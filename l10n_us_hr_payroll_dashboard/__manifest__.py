# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'US Payroll Dashboard',
    'version': '14.0.1',
    'category': 'Other',
    'author': 'Novobi',
    'summary': """Payroll Dashboard with things to do, manage employees and all payroll data""",
    'description': """Payroll Dashboard with things to do, manage employees and all payroll data""",
    'website': 'https://www.novobi.com',
    'depends': [
        'l10n_us_hr_payroll',
        'l10n_custom_dashboard',
    ],
    'data': [
        # ============================== DATA =================================
        'data/payroll_dashboard_data.xml',

        # ============================== SECURITY =============================
        'security/ir.model.access.csv',

        # ============================== VIEWS ================================
        'views/assets.xml',
        'views/payroll_dashboard_views.xml',
        'views/res_config_settings_views.xml',
    ],
    'demo': [],
    'qweb': ['static/src/xml/*.xml'],
    'installable': True,
    'application': False,
    'auto_install': False,
}
