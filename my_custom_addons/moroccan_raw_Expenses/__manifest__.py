{
    'name': 'Moroccan Raw Expenses',
    'version': '1.0',
    'summary': 'Classifies corporate expenses into the Moroccan Chart of Accounts via AI.',
    'category': 'Accounting',
    'author': 'Your Name',
    'depends': ['account'],
    'data': [
        'security/ir.model.access.csv',
        'views/raw_expenses_views.xml',
        
    ],
     'external_dependencies': {
        'python': ['litellm', 'pydantic', 'dotenv'],
    },
    'installable': True,
    'application': False,
}