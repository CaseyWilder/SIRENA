{
    'name': 'US Payroll: Timesheets',
    'version': '14.0.1',
    'category': 'Other',
    'author': 'Novobi',
    'summary': """Track and process US Payroll using Timesheets""",
    'description': """Track and process US Payroll using Timesheets""",
    'website': 'https://www.novobi.com',
    'depends': [
        'hr_timesheet',
        'l10n_us_hr_payroll',
    ],
    'data': [
        # ============================== DATA =================================

        # ============================== MENU =================================

        # ============================== VIEWS ================================
        'views/hr_employee_views.xml',
        'views/hr_timesheet_views.xml',
        'views/pay_period_views.xml',
        'views/payroll_payslip_views.xml',

        # ============================== SECURITY =============================

        # ============================== REPORT =============================

    ],
    'demo': [],
    'qweb': [],
    'installable': True,
    'application': False,
    'auto_install': False,
}
