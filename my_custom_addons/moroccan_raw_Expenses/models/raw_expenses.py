from odoo import models, fields
from odoo.exceptions import UserError
from litellm import completion
from pydantic import BaseModel, Field
import os
import logging
import time

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
    
    def action_categorize_ai(self):
        
        for record in self:
            
            system_prompt_step1 = (
                
                "You are an expert accountant specializing in the Moroccan Chart of Accounts (CGNC). "
                "Your task is to analyze raw business transaction text descriptions and map them directly to their correct 4-digit 'compte_principal'.\n\n"
                
                "CRITICAL UNIVERSAL RULES:\n"
                "1. CLASSIFY BY OBJECT NATURE: Always classify based on the physical or economic nature of the item being transacted, NOT the client/vendor's industry or secondary actions.\n"
                "2. MATERIAL FORM: Distinguish carefully between physical merchandise (bought for resale as-is), raw materials (bought for factory production/transformation), and intangible services.\n\n"
                
                
            )

            
            time.sleep(3)
            try:
                response1 = completion(
                    model = 'gemini/gemini-3.5-flash',
                    fallbacks= [   
                        'gemini/gemini-2.5-pro',     
                        'gemini/gemini-2.5-flash',               
                    ],
                    api_key = api_key,
                    messages = [
                                {"role": "system", "content": system_prompt_step1}, #"You are an expert accountant specializing in the Moroccan Chart of Accounts (CGNC). Your task is to analyze raw business transaction text descriptions and map them to their correct 4-digit Principal Account Code.\n\nCRITICAL UNIVERSAL RULES:\n1. CLASSIFY BY OBJECT NATURE: Always classify based on the physical or economic nature of the item being transacted, NOT the client/vendor's industry or secondary actions (e.g., selling physical factory waste, scrap, or byproducts is a sale of physical goods, NOT a service).\n2. MATERIAL FORM: Distinguish carefully between physical merchandise (bought for resale as-is), raw materials (bought for factory production/transformation), and intangible services."}, # system prompt that containes the rules that the llm should follow
                                {"role": "user", "content": f"Classify this business transaction: '{record.name}'"} # user prompt that contains the dynamic data to be analyzed by the llm
                                ],
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
                
                
                # One2many tables iare accessed like this (line_ids represents a row in the table)
                'line_ids': [ 
                    # Line 1: The Debit (The AI's chosen expense account)
                    (0,0,{ # first 0 is if create, secod 0 is for the id, and the third argument is the data to post as a pythin dict.
                        'account_id': record.account_id.id,
                        'name': record.name,
                        'debit': record.amount,
                        'credit': 0.0
                    }),
                    # Line 2: The Credit (Where the money came from, e.g., Cash/Bank)
                    (0,0,{
                        # for now we hardcode the 
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
                record.state = 'posted'
            else:
                raise UserError(f"failed to create a journal entry for {record.name}")