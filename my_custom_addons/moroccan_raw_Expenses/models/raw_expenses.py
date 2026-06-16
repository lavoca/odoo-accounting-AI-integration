from odoo import models, fields


class RawExpences(models.Model):
    _name = 'moroccan.raw.expenses'
    _description = 'Raw Expenses'
    
    name = fields.Char(string="Expense Description", required=True, default="new expense")
    date = fields.Date(string="Date", default=fields.Date.today)
    amount = fields.Float(string="Amount")
    account_id = fields.Many2one('account.account', string="Account")
    state = fields.Selection([('draft','Draft'),('categorized','Categorized')], default='draft')
    