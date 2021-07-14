{
    'name': 'US Payroll: Checks Layout for payslip',
    'version': '14.0.1',
    'category': 'Accounting',
    'author': 'Novobi',
    'summary': 'US Checks for payslip',
    'description': """
Supported formats
-----------------
This module supports the three most common check formats and will work out of the box with the linked checks from checkdepot.net.

View all checks at: https://www.checkdepot.net/checks/laser/Odoo.htm

You can choose between:

- Check on top: Quicken / QuickBooks standard (https://www.checkdepot.net/checks/checkorder/laser_topcheck.htm)
- Check on middle: Peachtree standard (https://www.checkdepot.net/checks/checkorder/laser_middlecheck.htm)
- Check on bottom: ADP standard (https://www.checkdepot.net/checks/checkorder/laser_bottomcheck.htm)
    """,
    'website': 'https://www.novobi.com',
    'depends': [
        'l10n_us_check_printing',
        'l10n_us_hr_payroll_reports',
    ],
    'data': [
        # ============================== SECURITY =============================
        'security/ir.model.access.csv',

        # ============================== DATA =================================
        'data/ir_exports_data.xml',
        'data/report_data.xml',
        'data/mail_template_data.xml',

        # ============================== VIEWS ================================
        'views/res_config_settings_views.xml',
        'views/pay_period_views.xml',
        'views/payroll_payslip_views.xml',

        # ============================== WIZARD ================================
        'wizard/print_check_paystub_wizard.xml',

        # ============================== REPORT ================================
        'report/report_templates.xml',
        'report/check_templates.xml',
        'report/paystub_templates.xml',
    ],
    'installable': True,
    'auto_install': False,
}
