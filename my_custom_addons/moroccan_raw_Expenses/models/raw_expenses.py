from odoo import models, fields, api
from odoo.exceptions import UserError
from litellm import completion
from pydantic import BaseModel, Field
import os
import logging
import time
from datetime import timedelta

_logger = logging.getLogger(__name__)

class AccountDetails(BaseModel):
    operation_meaning: str = Field(description="Explain what physical or intangible object is being transacted in plain words (e.g., 'Selling production-line waste metal scraps').")    
    operation: str = Field(description="The nature of the business operation, strictly either 'Produits' or 'Charges'.")
    accountclass: int = Field(description="The single-digit class code (e.g., 6 or 7) that determines which side of the CPC table the transaction belongs to.")
    compte_principal: str = Field(description="The exact 4-digit principal account code according to the CGNC hierarchy matching your analysis (must be a 4-character string, e.g., '7121' or '6125').")
    reasoning: str = Field(description="The accounting reason and justification for choosing this specific 4-digit principal account code.")


class AccountCode(BaseModel):
    accountnumber: str = Field(description="The exact full 6-digit account code selected directly from the provided pool list string.")
    reasoning: str = Field(description="The short reason you chose this specific code out of the available pool options.")
    
api_key = os.environ.get('GEMINI_API_KEY')
    
class RawExpenses(models.Model):
    _name = 'moroccan.raw.expenses'
    _description = 'Raw Expenses'
    
    name = fields.Char(string="Expense Description", required=True, default="new expense")
    date = fields.Date(string="Date", default=fields.Date.today)
    amount = fields.Float(string="Amount", required=True)
    account_id = fields.Many2one('account.account', string="Account")
    operation = fields.Char(string="operation kind")
    Class = fields.Char(string="class")
    rubric = fields.Char(string="principal account")
    reason1 = fields.Text(string="AI reasoning")
    reason2 = fields.Text(string="AI reasoning")
    state = fields.Selection([('draft','Draft'), ('categorized','Categorized'), ('posted', 'Posted')], default='draft')
    # field that connects/links an expense to its posted journal entry in the account.move model
    move_id = fields.Many2one('account.move', string="Journal Entry", readonly=True)
    # computed field that has a dynamic value controlled by a function in the computed argument in this case its "_compute_is_out_of_sync" 
    # compute="_compute_is_out_of_sync" tells odoo to run the function when we read this field in the database or when the view page is refreshed 
    is_updates_sync = fields.Boolean(string="update Out of Sync", compute="_compute_is_out_of_sync")
    # the active company for a given recrod
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)
            
    
    def action_categorize_ai(self):
        
        for record in self:
           
            # search for all the accounts that start with either 7 or 6 representing the accounts in class 7 and 6
            accounts = self.env['account.account'].search(['|', ('code', '=like', '6%'), ('code', '=like', '7%')])
            # the dictionary where we will store the 4 digits accounts
            rubric_map = {}
            # for every account we found we need to extract the 4 first digits and insert them into the dictionary as keys with the names as values 
            for acc in accounts:
                if acc.code and len(acc.code) >=4: # .code gets the string inside 
                    four_digit_code = acc.code[:4]
                    # check if the 4 digit code is not in the map dictionary to create a new set for it
                    if four_digit_code not in rubric_map:
                        # Initialize an empty set if this 4-digit root isn't in the map yet that will hold the names of the account that belong to every 4 digit code
                        rubric_map[four_digit_code] = set()
                        
                    # Add the full name string directly to the set (prevents identical duplicates)
                    if acc.name:
                        rubric_map[four_digit_code].add(acc.name.strip())
                    
            # 2. Compile the sets into clean, full-sentence layout blocks for the LLM
            pool_lines = []
            for root_code in sorted(rubric_map.keys()):
                # Join all unique full names with a semicolon
                combined_names = "; ".join(sorted(list(rubric_map[root_code])))
                pool_lines.append(f"{root_code} : [{combined_names}]")  
            dynamic_parent_map = "\n".join(pool_lines)
            
            system_prompt_step1 = (
                "You are an expert accountant specializing in the Moroccan Chart of Accounts (CGNC). "
                "Your task is to analyze raw business transaction text descriptions and map them directly to their correct 4-digit 'compte_principal'.\n\n"
                "AVAILABLE ACCOUNTS DICTIONARY:\n"
                f"{dynamic_parent_map}\n\n"
                "CRITICAL SELECTION RULES:\n"
                "1. You MUST choose a 4-digit code that exists exactly as a prefix in the AVAILABLE ACCOUNTS DICTIONARY.\n"
                "2. Analyze the economic nature of the transaction (e.g., check for export/abroad keywords vs. domestic names, "
                "or raw materials vs. finished products) and match it to the most descriptive title in the dictionary."
            )
            
            messages_payload = [
                {"role": "system", "content": system_prompt_step1},  # system prompt that containes the rules that the llm should follow
                {"role": "user", "content": f"Classify this business transaction: '{record.name}'"} # user prompt that contains the dynamic data to be analyzed by the llm
            ]

            # 2. LOG THE LOCAL UNBIASED TEXT DICTIONARY GENERATED FROM ODOO
            _logger.info("================ [LOCAL ODOO DATA] DYNAMIC DICTIONARY MAP ================")
            _logger.info("\n%s", dynamic_parent_map)
            _logger.info("==========================================================================")

            # 3. LOG THE EXACT STRING CONTENT SENT TO THE OUTBOUND API FOR REVIEW
            _logger.info("================ [OUTBOUND API] FULL STEP 1 PROMPTS SENT =================")
            for msg in messages_payload:
                _logger.info("ROLE: %s | CONTENT: %s", msg['role'].upper(), msg['content'])
            _logger.info("==========================================================================")

            
            time.sleep(3)
            try:
                response1 = completion(
                    model = 'gemini/gemini-2.5-flash',
                    fallbacks= [   
                        'gemini/gemini-2.5-pro',     
                        'gemini/gemini-3.5-flash',               
                    ],
                    api_key = api_key,
                    messages = messages_payload,
                    response_format = AccountDetails,
                    temperature = 0.5
                )
            except Exception as e:
                # Log the messy technical details in the Odoo server terminal for debugging
                _logger.error("Gemini API Connection failed at the FIRST STEP: %s", e)
                # Show a clean, professional, non-crashing alert to the Moroccan accountant
                raise UserError("Impossible de contacter le service d'intelligence artificielle. Veuillez vérifier votre connexion ou réessayer dans quelques instants.")
            
            # the returned data from the llm is in form of a json string so we should convert it to a pyhton object
            raw_llm_result1 = response1.choices[0].message.content
            
            # Force Pydantic to parse the string into a live object!
            # so we can use . dot-notation to access elements inside the llm returned result data
            llm_result1 = AccountDetails.model_validate_json(raw_llm_result1)
            
            # search for every 6 digit code that belongs to the 4 digit rubric code returned by the llm
            rubrics = self.env['account.account'].search([('code', '=like', f'{llm_result1.compte_principal}%')])
            
            if rubrics:
                # make a list of the 6 digit codes found in the odoo database to pass the the second step llm call so we can provide the llm with accurate odoo accounts to choose from
                rubrics_pool = [f"{a.name} - {a.code}" for a in rubrics]
                # assign the data to the record fields to appear in the view xml
                record.operation = llm_result1.operation
                record.Class = llm_result1.accountclass
                record.rubric = llm_result1.compte_principal
                record.reason1 = llm_result1.reasoning
                
            else:
                raise UserError(f"AI returned code {llm_result1.compte_principal}, but it doesn't exist in Odoo's Chart of Accounts!\n "
                                f"the reasoning is: {llm_result1.reasoning}\n"
                                )
            
            
            system_prompt_step2 = (
                f"You are an expert accountant specializing in the Moroccan Chart of Accounts (CGNC). "
                f"Your task is to match raw business transaction text descriptions and map them directly to the active Odoo 6-digit Moroccan accounting code "
                f"from the following provided list: {rubrics_pool}\n\n"
                
                f"STRICT SELECTION RULES:\n"
                f"1. You MUST pick a 6-digit code that exists exactly inside the provided list. Do not invent any digits.\n"
                f"2. If an exact matched phrase is missing, select the closest logical category or the general 'Other/Miscellaneous' fallback account present in the list (e.g., codes ending in 80 or 90)."
            )
            user_prompt = f"Analyze and classify this business transaction: '{record.name}'"
                        
            account = False
            
            time.sleep(3)
            try:
                response = completion(
                    model = 'gemini/gemini-2.5-flash-lite',
                    fallbacks= [
                        "gemini/gemini-3.1-flash-lite",                      
                    ],
                    api_key = api_key,
                    messages = [
                                {"role": "system", "content": system_prompt_step2}, # system prompt that containes the rules that the llm should follow
                                {"role": "user", "content": user_prompt} # user prompt that contains the dynamic data to be analyzed by the llm
                                ],
                    response_format = AccountCode,
                    temperature = 0.4
                )
            except Exception as e:
                # Log the messy technical details in the Odoo server terminal for debugging
                _logger.error("Gemini API Connection failed at the SECOND STEP: %s", e)
                # Show a clean, professional, non-crashing alert to the Moroccan accountant
                raise UserError("Impossible de contacter le service d'intelligence artificielle. Veuillez vérifier votre connexion ou réessayer dans quelques instants.")
            
            
            # the returned data from the llm is in form of a json string so we should convert it to a pyhton object
            raw_llm_result = response.choices[0].message.content
            
            # Force Pydantic to parse the string into a live object!
            # so we can use . dot-notation to access elements inside the llm returned result data
            llm_result = AccountCode.model_validate_json(raw_llm_result)
            
            
            # search the odoo internal database of a model for the account number from the llm  
            # the account number from the llm is a python type and we need an odoo account type that is why we search using the account from the llm the chart of accounts
            account = self.env['account.account'].search([('code', '=', llm_result.accountnumber)], limit=1)

            if account:
                # assign the data to the record fields to appear in the view xml
                record.account_id = account
                record.reason2 = llm_result.reasoning
                record.state = 'categorized'
            else:
                raise UserError(
                    
                                f"AI returned code {llm_result.accountnumber}, but it doesn't exist in Odoo's Chart of Accounts!\n "
                                f"reasoning for the first step: {llm_result1.reasoning}\n"
                                f"the reasoning for the second step: {llm_result.reasoning}\n"
                            )
                
    def action_post_to_accounting(self):
        
        for record in self:
            journal = self.env['account.move'].create({
                
                'move_type': 'entry', # choose to create into the journal entry database of the account.move model
                'ref': record.name,
                'date': record.date,
                
                
                # One2many tables are accessed like this (line_ids represents a row in the table)
                'line_ids': [ 
                    # Line 1: The Debit (The AI's chosen expense account)
                    (0,0,{ # first 0 is if create, second 0 is for the id, and the third argument is the data to post as a python dict.
                        'account_id': record.account_id.id,
                        'name': record.name,
                        'debit': record.amount,
                        'credit': 0.0
                    }),
                    # Line 2: The Credit (Where the money came from, e.g., Cash/Bank)
                    (0,0,{
                        # for now we hardcode the account related to where the money came from 
                        'account_id': self.env['account.account'].search([('code', '=like', '5161%')], limit=1).id,
                        'name': record.name,
                        'debit': 0.0,
                        'credit': record.amount,
                    })
                ]
            })
            if journal:
                # auto post the journal entry so it is not a draft
                # lets comment it for now since we want the user to still review the entry before clicking post
                #journal.action_post()
                record.move_id = journal.id
                record.state = 'posted'
            else:
                raise UserError(f"failed to create a journal entry for {record.name}")
            
    # function that updates an existing journal entry from its expense 
    # the way it is done is we delete the existing Entry for the given record then repost it with the new data by reccaling the post function       
    # IMPORTANT: we only update journal entries that are still in a 'draft' state
    def action_update_accounting(self):
        for record in self:
            # check if the record has an journal entry or not by using the move_id link that connects/points to the journal entries of a given record (raw expense)
            if not record.move_id:
                raise UserError("There is not Journal Entry for this record yet.\n Post it to create an entry.")
            # check id the record's journal entry is already posted and not in a 'draft' state
            if record.move_id.state == 'posted':
                raise UserError("This Entry has been posted already, it cannot be changed")
            
            # if the code reaches here then it means we can safley delete the journal entry using unlink on move_id which points to the journal entry of the record
            record.move_id.unlink()
            
            # after the deletion we create a new journal entry using the new data by calling the normal post function
            record.action_post_to_accounting()
            
            
    # this function is responseble for updating the journal entry upon changes in the expense fileds
    # @api.depends tells Odoo: "Run this function instantly whenever any of these fields change"
    # IMPORTANT: @api.depends triggers the function when a field changes in real time but we also need compute="_compute_is_out_of_sync" so it triggers the function the page reloads or when we read the field in the database
    @api.depends('name', 'date', 'amount', 'account_id', 'state', 'move_id.ref', 'move_id.date', )
    def _compute_is_out_of_sync(self): # watches the expenses fields if any of them changes we run this to make the update button visible in the view
        
        for record in self:
            
            # the fields that get posted to the journal entry from expense are four (name, date, account_id and amount) so we only check for these fields if they are different
            
            record.is_updates_sync = False # the button state starts as false/invisible
            
            if not record.move_id or record.state != 'posted': # if this is true then we dont have anything to update anyway so we skip this record
                continue
            
            # check the header fileds outside the table in the journal entry
            if record.name != record.move_id.ref or record.date != record.move_id.date:
                record.is_updates_sync = True 
                
            # find the exact line in the table that has the debit amount related to the record.amount by matching the account name
            journal_table_data = record.move_id.line_ids.filtered(lambda line: line.account_id == record.account_id)
            
            
            # if we dont find it then the data is different thus we need to update
            # this also acts as a way to check if the account_id is different in the table so we can update
            if not journal_table_data:
                record.is_updates_sync = True
                
            # if we find it then check if the debit amount is different if yes update if no then we dont need to show the update button 
            elif journal_table_data[0].debit != record.amount:
                record.is_updates_sync = True
                
                
    # @api.model tells odoo: this method runs on the whole model/record and not on only one record that is why we didnt loop over self like we always do becasue we are applying this to the whole model and its records        
    @api.model
    def _cron_cleanup_old_drafts(self):
        
        thirty_days_ago = fields.Date.today() - timedelta(days=30) # calculate the date 30 days ago in odoo
        
        month_older_drafts = self.search([ # search query on the whole model
            ('state', '=', 'draft'), # search for the records that are still in draft state
            ('date', '<', thirty_days_ago) # '<' means older than, so we search for records older than 30 days
        ])
        
        if month_older_drafts:
            _logger.info(f"CRON: Deleting {len(month_older_drafts)} old draft expenses.")
            month_older_drafts.unlink() # unlink() is how we delete in odoo