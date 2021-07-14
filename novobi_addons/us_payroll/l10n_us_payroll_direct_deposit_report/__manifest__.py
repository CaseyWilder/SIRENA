{
    'name': 'US Payroll: Direct Deposit Report',
    'version': '14.0.1',
    'category': 'Other',
    'author': 'Novobi',
    'summary': """Generate direct deposit report for payroll""",
    'description': """Generate direct deposit report for payroll""",
    'website': 'https://www.novobi.com',
    'depends': ['l10n_us_hr_payroll'],
    'data': [
        # ============================== DATA =================================

        # ============================== MENU =================================

        # ============================== VIEWS ================================
        'wizard/print_direct_deposit_wizard.xml',
        'views/pay_period_views.xml',

        # ============================== SECURITY =============================
        'security/ir.model.access.csv',

        # ============================== REPORT =============================
        'report/direct_deposit_report.xml',

    ],
    'demo': [],
    'qweb': [],
    'installable': True,
    'application': False,
    'auto_install': False,
}
