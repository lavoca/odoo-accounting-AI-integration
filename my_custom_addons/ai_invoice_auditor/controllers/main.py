import json
from odoo import http
from odoo.http import request

# In Odoo, controllers must inherit from http.Controller
class AIAuditController(http.Controller):
    
    # inside the controllers slef.env doesnt exist becasue the class doesnt inherit from models.Model but we inherit from http.Controller snd self is an ORM recordset inside an odoo table
    # so to talk to the odoo database we have to use request.env because the request object represents the incoming HTTP web request and holds the user session and database environment

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