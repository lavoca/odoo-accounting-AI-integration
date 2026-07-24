import logging
from odoo import models, fields, api
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class AccountMove(models.Model):
    _inherit = 'account.move'
    
    # This creates a new column in the 'account_move' table
    bypass_ai_check = fields.Boolean(string="Bypass AI Audit", default=False)

    def action_post(self):
        customer_name = self.partner_id.name
        total_amount = self.amount_total
        currency = self.currency_id.name

        # Package the data for the AI call
        invoice_data = {
            "customer": customer_name,
            "total": total_amount,
            "currency": currency,
            "items": []
        }

        for line in self.invoice_line_ids:
            if line.product_id:
                invoice_data["items"].append({
                    "product": line.product_id.name,
                    "qty": line.quantity,
                    "price": line.price_unit
                })

        # MOCK AI CHECK: Let's pretend the AI flags any invoice over $200
        _logger.info("Sending data to AI: %s", invoice_data)
        
        is_fraud = False
        if total_amount > 200:
            is_fraud = True  # The AI thinks this is suspicious!

        # Block the confirmation if fraud is detected
        # Only raise the error if the checkbox is NOT checked
        if is_fraud and not self.bypass_ai_check:
            # --- THE MAGIC TRICK: Open a new database cursor ---
            with self.env.registry.cursor() as new_cr:
                # Create a new 'Environment' that uses this new cursor
                new_env = api.Environment(new_cr, self.env.uid, self.env.context)
                
                # Save the log to the ai.audit.log table we created using the NEW environment
                new_env['ai.audit.log'].create({
                    'name': "BLOCKED: High Value",
                    'invoice_id': self.id,
                    'customer_id': self.partner_id.id,
                    'amount_total': total_amount,
                    'reason': f"AI flagged amount of {total_amount} {currency} as suspicious."
                })
           

            # Now raise the error. This destroys the main transaction, 
            # but our secret transaction above is already safely saved!
            raise UserError(f"🚨 AI AUDIT FAILED: High amount detected. Check 'Bypass AI Audit' to proceed.")

        # 5. If no fraud, proceed normally
        return super(AccountMove, self).action_post()
    
    
        
        