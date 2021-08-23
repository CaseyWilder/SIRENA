# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'US Payroll: Expenses',
    'version': '14.0.1',
    'category': 'Other',
    'author': 'Novobi',
    'summary': """Manage US Payroll Expenses""",
    'description': """Manage US Payroll Expenses""",
    'website': 'https://www.novobi.com',
    'depends': [
        'hr_expense',
        'l10n_us_hr_payroll',
    ],
    'data': [
        # ============================== SECURITY =============================
        'security/ir.model.access.csv',

        # ============================== DATA =================================

        # ============================== MENU =================================

        # ============================== VIEWS ================================
        'views/pending_compensation.xml',
        'views/hr_expense_sheet_views.xml',
        'views/pay_period_views.xml',
        'views/res_config_settings_views.xml',

        # ============================== WIZARD =============================
        'wizard/add_missing_comp_wizard_views.xml',

        # ============================== REPORT =============================

    ],
    'demo': [],
    'qweb': ['static/src/xml/*.xml'],
    'installable': True,
    'application': False,
    'auto_install': False,
}
