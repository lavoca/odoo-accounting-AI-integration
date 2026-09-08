{
    'name': 'AI Invoice Auditor',
    'version': '1.0',
    'summary': 'Intercepts and audits invoices using AI before validation.',
    'category': 'Accounting',
    'author': 'Your Name',
    'license': 'GPL-3',
    'depends': ['account'],
    'data': [
        'security/ir.model.access.csv',
        'views/account_move_views.xml',
        'views/audit_log_views.xml',
        'views/audit_log_report.xml'
    ],
    'installable': True,
    'application': False,
}
