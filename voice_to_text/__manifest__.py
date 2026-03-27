{
    'name': 'Voice to Text',
    'version': '17.0.1.0.7',
    'category': 'Uncategorized',
    'summary': 'Voice to Text',
    'description': """
        Este modulo agrega ciertas funcionalidades relacionadas con la conversion de voz a texto.
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
        #'views/global_voice_assistant.xml',
        # 'reports/payment_voucher_report.xml',
        'security/ir.model.access.csv',
        'views/voice_command_config_views.xml',
        # 'views/res_user_views.xml',
        # 'views/hms_patient_views.xml',
        'views/res_config_settings_views.xml',
        'wizards/search_patient_wizard_views.xml'
    ],
    'assets': {
        'web.assets_backend': [
            # 'voice_to_text/static/lib/fuse.basic.min.js',
            # 'voice_to_text/static/src/components/ai_completion.js',
            # 'voice_to_text/static/src/components/ai_completion.xml',
            'voice_to_text/static/src/components/global_voice_assistant.xml',
            'voice_to_text/static/src/components/global_voice_assistant.js',
            'voice_to_text/static/src/components/search_bar_voice.js',
            'voice_to_text/static/src/components/search_bar_voice_views.xml',
            # 'voice_to_text/static/src/components/proof_thesis.js',
            # 'voice_to_text/static/src/components/proof_thesis.xml',
            'voice_to_text/static/src/css/voice_styles.css'
        ],
    },
    'installable': True,
    'application': False,
}