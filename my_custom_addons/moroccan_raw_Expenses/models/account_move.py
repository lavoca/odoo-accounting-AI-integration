from odoo import models, fields



class AccountMove(models.Model):
    
    _inherit = 'account.move'
    # filed that links a journal entry to its raw expense that created it, this is a "one to many" field so we specify which of the table we want to fetch (move_id)
    expense_id = fields.One2many('moroccan.raw.expenses', 'move_id', string="raw expense", readonly=True)
    
    # a set of changes we look for (we made them as sets becasue we are going to use sets operations like & to compare between two sets changes and vals after we conver it to a set)
    changes = {'ref', 'date', 'line_ids'} # the name of the fields that may have changed thus can be found inside vals dictionary

    def write(self, vals): # vals is a dictionary of key value pairs, keys represent the field names that changed and values represent the new data
        
        # save the changes for the current account.move model like normal before we expose the changes to the expense model
        res = super(AccountMove, self).write(vals)
        
        # convert vals into a set type so we can use comparison operators on it with other sets
        # acess variables outside the write func or any sub func using self.
        if set(vals) & self.changes: # & is an intersection operator that returns true if a set has its elements inside another set, basically if set A contains any element in set B 
            
            for move in self: # loop over the journal entries 
                
                # move.expense_id here is technically just one expense linked to our entry but the way odoo database is built it is a list with one item so we have to loop over it 
                for linked_expense in move.expense_id: 
                    
                    # dict to hold our updates that we will send and apply to the raw expense 
                    updates = {}
                    
                    if 'ref' in vals:
                        updates['name'] = move.ref  # the key is the field name in the expense model and the value is the data in journal entry for the equivalent field 
                        move.line_ids.write({'name': move.ref}) # we wna to update the label field in the table as well to match the ref filed above it and since there are many lines in the table that have the lable field we should use write method
                    if 'date' in vals:
                        updates['date'] = move.date
                        
                        
                    # to access the table fields in the journal entry we need to traverse how vals represents them
                    # when a field in the table changes it is represented in vals as a key value pair with 'line_ids' as the key and the value is a list of tuples
                    # each tuple represents a record and inside the tuple there is three values the first is the command second is the record is the third is a dict of the fields that changed
                    # we want to access the third tuple at index 2 that holds the fields that changed 
                    
                    if 'line_ids' in vals:
                        
                        line_ids = vals['line_ids'] # get hold of the table changes array in the vals dict
                        
                        for line_tuple in line_ids: # loop over the array of tuples 
                            
                            if line_tuple[0] == 1: # we only care about updates to fileds and that is represented with code 1 in the first tuple at index 0 (if the code is 0 it means create if its 2 it means delete)
                                
                                # the third tuple at index 2 is the one holding the changes to the fileds as form of a dictionary
                                for field, value in line_tuple[2].items(): # get hold of the (field, changes) pairs 
                                    
                                    match field:
                                        case 'account_id':
                                            updates['account_id'] = value
                                        case 'name':
                                            updates['name'] = value
                                            # keep in mind this triggers write() again since we changed a field and there is a danger of infinite loop but odoo automatically protects against that by checking if the field is the same before calling write again on the same model
                                            move.ref = value
                                        case 'debit' | 'credit':
                                            updates['amount'] = value
                                        
                                        
                                    
                    linked_expense.write(updates) # call write methode that saves the model on the expense model
        return res
        