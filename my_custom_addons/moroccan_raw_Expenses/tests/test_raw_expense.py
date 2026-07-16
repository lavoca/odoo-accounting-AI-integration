from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError


# Inherit from TransactionCase so Odoo knows this is a test and will roll back the database after
class TestRawExpense(TransactionCase):
    
    # the setUp() function runs before every test so if we want to rin some code before the test begins we do it inside
    # we use it to create mock data for the test
    def setUp(self):
        
        super(TestRawExpense, self).setUp()
        
        # create a fake account just for this test, this account will get deleted after the test becasue of the rollback
        self.mock_account = self.env['account.account'].create({
            'code': '614299',
            'name': 'Mock Fuel Account',
            'account_type': 'expense' 
        })
        
        # create a mock raw expense 
        self.expense = self.env['moroccan.raw.expenses'].create({
            'name': 'Test Achat Carburant',
            'amount': 500.0,
            'account_id': self.mock_account.id,
            # We manually set it to 'categorized' to pretend the AI already did its job
            'state': 'categorized' 
        })
        
        # a tets function name must always start with test_
        def test_action_post_to_accounting(self):
            
            # Every function that starts with 'test_' will be run automatically.
            
            # Click the button via code to post to journal entry
            self.expense.action_post_to_accounting()
            
            # Use standard Python 'assert' to check if the code did what we expected
            
            # check if the state changed to posted
            self.assertEqual(self.expense.state, 'posted', "The expense state should be 'posted' after clicking the button.")
            
            # check if it a journal entry got created and linked via move_id
            self.assertTrue(self.expense.move_id, "A Journal Entry should have been created and linked to the expense.")
            
            # Does the Journal Entry have the correct amount?
            # (check the debit on the first line)
            expense_line = self.expense.move_id.line_ids.filtered(lambda l: l.account_id == self.mock_account)
            self.assertEqual(expense_line.debit, 500.0, "The Journal Entry debit amount must match the expense amount.")