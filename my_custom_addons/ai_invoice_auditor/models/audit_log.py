from odoo import models, fields

class AIAuditLog(models.Model):
    # _name creates a BRAND NEW table in the database called 'ai_audit_log'
    _name = 'ai.audit.log'
    _description = 'AI Audit Log'
    
    # Odoo automatically adds standard fields like 'create_date', but we define our custom ones:
    name = fields.Char(string="Log Reference", required=True, default="New Audit")
    
    # This is Odoo's version of a Foreign Key linking to the Invoice table
    invoice_id = fields.Many2one('account.move', string="Invoice", required=True)
    
    # We can also link directly to the Customer table
    customer_id = fields.Many2one('res.partner', string="Customer")
    
    amount_total = fields.Float(string="Total Amount")
    reason = fields.Text(string="Flag Reason")