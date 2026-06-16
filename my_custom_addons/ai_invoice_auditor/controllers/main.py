import json
from odoo import http
from odoo.http import request

# In Odoo, controllers must inherit from http.Controller
class AIAuditController(http.Controller):

    # @http.route is the router. It defines the URL, the type of request, and the security.
    @http.route('/api/audits', type='http', auth='user', methods=['GET'], csrf=False)
    def get_audit_logs(self, **kwargs):
        
        # 1. Fetch data from the database. 
        # Notice we use 'request.env' here instead of 'self.env'
        audit_logs = request.env['ai.audit.log'].search([])

        # 2. Format the data into a list of dictionaries
        data = []
        for log in audit_logs:
            data.append({
                "id": log.id,
                "invoice": log.invoice_id.name,
                "title": log.name,
                "amount": log.amount_total,
                "reason": log.reason
            })

        # 3. Return a standard JSON response
        return request.make_response(
            json.dumps(data), 
            headers=[('Content-Type', 'application/json')]
        )