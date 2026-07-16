{
    'name': 'Moroccan Raw Expenses',
    'version': '1.0',
    'summary': 'Classifies corporate expenses into the Moroccan Chart of Accounts via AI.',
    'category': 'Accounting',
    'author': 'Your Name',
    'depends': ['account'],
    'data': [
        'security/ir.model.access.csv',
        'security/security_rules.xml',
        'data/cron_job.xml',
        'views/raw_expenses_views.xml',
        'views/account_move_expense_link.xml',
        
    ],
     'external_dependencies': {
        'python': ['litellm', 'pydantic', 'dotenv'],
    },
    'installable': True,
    'application': False,
}