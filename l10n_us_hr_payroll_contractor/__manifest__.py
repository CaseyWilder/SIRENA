# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'US Payroll: Contractors',
    'version': '14.0.1',
    'category': 'Other',
    'author': 'Novobi',
    'summary': """Manage US Payroll Contractors""",
    'description': """Manage US Payroll Contractors""",
    'website': 'https://www.novobi.com',
    'depends': [
        'l10n_us_hr_payroll',
        'l10n_us_hr_payroll_reports',
        'l10n_us_hr_payroll_dashboard'
    ],
    'data': [
        # ============================== SECURITY =============================

        # ============================== DATA =================================

        # ============================== MENU =================================

        # ============================== VIEWS ================================
        'views/hr_employee_views.xml',
        'views/payroll_payslip_views.xml',
        'views/pay_period_views.xml',

        # ============================== WIZARD =============================

        # ============================== REPORT =============================

    ],
    'demo': [],
    'qweb': ['static/src/xml/*.xml'],
    'installable': True,
    'application': False,
    'auto_install': False,
}
