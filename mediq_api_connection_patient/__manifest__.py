{
    'name': 'Mediq Api Connection Patient',
    'version': '17.0.1.0.7',
    'category': 'Uncategorized',
    'summary': 'Mediq Api Connection Patient',
    'description': """
        Este modulo se encarga de con
    """,
    'author': 'Tribu System',
    'website': 'https://www.tribusystem.com',
    'license': 'Other proprietary',
    'depends': [
        'base',
        'web',
        'acs_hms'
    ],
    'data': [
        # 'security/ir.model.access.csv',
        'views/res_user_views.xml',
        'views/hms_patient_views.xml',
    ],
    'installable': True,
    'application': False,
}