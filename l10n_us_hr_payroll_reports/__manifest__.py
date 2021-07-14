# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'US Payroll: Reports',
    'version': '14.0.1',
    'category': 'Other',
    'author': 'Novobi',
    'summary': """Generate and manage payroll reports""",
    'description': """Generate and manage payroll reports""",
    'website': 'https://www.novobi.com',
    'depends': ['l10n_us_hr_payroll'],
    'data': [
        # ============================== SECURITY =============================
        'security/ir.model.access.csv',
        'security/ir_rule.xml',

        # ============================== DATA =================================
        'data/payroll_summary_report_data.xml',
        'data/ir_exports_data.xml',

        # ============================== VIEWS ================================
        'views/assets.xml',
        'views/payroll_payslip_views.xml',
        'views/pay_period_views.xml',
        'views/quarter_tax_report_views.xml',
        'views/wage_tax_report_views.xml',
        'views/semiweekly_tax_report_views.xml',
        'views/hr_employee_views.xml',
        'views/paycheck_report_views.xml',

        # ============================== WIZARDS ================================
        'wizard/quarter_tax_report_wizard_views.xml',
        'wizard/wage_tax_report_wizard_views.xml',
        'wizard/semiweekly_tax_report_wizard_views.xml',

        # ============================== MENU =================================
        'views/report_menu.xml',

        # ============================== REPORT =============================
        'report/quarter_tax_report_template.xml',
        'report/semiweekly_tax_report_template.xml',
        'report/wage_tax_report_template.xml',
    ],
    'demo': [],
    'qweb': [],
    'installable': True,
    'application': False,
    'auto_install': False,
}
