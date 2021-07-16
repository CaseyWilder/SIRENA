# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'US Payroll',
    'version': '14.0.1',
    'category': 'Other',
    'author': 'Novobi',
    'summary': """Manage US Payroll""",
    'description': """Manage US Payroll""",
    'website': 'https://www.novobi.com',
    'depends': [
        'base',
        'hr_attendance',
        'account_accountant',
        'l10n_generic_coa',
        'l10n_us_hr_holidays',
    ],
    'data': [
        # ============================== SECURITY =============================
        'security/l10n_us_hr_payroll_security.xml',
        'security/ir.model.access.csv',
        'security/ir_rule.xml',

        # ============================== DATA =================================
        'data/init_data.xml',
        'data/ir_config_parameter_data.xml',
        'data/compensation_category_data.xml',
        'data/compensation_data.xml',
        'data/deduction_type_data.xml',
        'data/deduction_category_data.xml',
        'data/deduction_data.xml',
        'data/hr_holidays_data.xml',
        'data/ir_cron_data.xml',
        'data/ir_sequence_data.xml',
        'data/res_country_state_data.xml',
        'data/hr_employee_data.xml',
        'data/pay_period_data.xml',

        # ============================== VIEWS ================================
        'views/payroll_onboarding_templates.xml',
        'views/templates.xml',
        'views/res_partner_views.xml',
        'views/res_bank_view.xml',
        'views/account_journal_view.xml',
        'views/compensation_views.xml',
        'views/deduction_views.xml',
        'views/deduction_policy_views.xml',
        'views/deduction_enrollment_policy_views.xml',
        'views/employee_deduction_views.xml',
        'views/employee_compensation_views.xml',
        'views/account_payment_direct_views.xml',
        'views/time_tracking_rule_views.xml',
        'views/hr_employee_views.xml',
        'views/hr_department_views.xml',
        'views/hr_attendance_views.xml',
        'views/hr_leave_type_views.xml',
        'views/hr_leave_views.xml',
        'views/hr_leave_allocation_views.xml',
        'views/pay_frequency_views.xml',
        'views/pay_period_views.xml',
        'views/payslip_deduction_views.xml',
        'views/payslip_garnishment_views.xml',
        'views/payslip_compensation_views.xml',
        'views/payslip_tax_views.xml',
        'views/payroll_payslip_views.xml',
        'views/tax_views.xml',
        'views/filing_status_view.xml',
        'views/sui_tax_views.xml',
        'views/res_company_views.xml',
        'views/res_config_settings_views.xml',
        'views/resource_views.xml',

        # ============================== MENU =================================
        'views/payroll_menu_view.xml',

        # ============================== WIZARD =============================
        'wizard/open_payroll_report_wizard_views.xml',
        'wizard/hr_departure_wizard_view.xml',
        'wizard/create_historical_period_wizard_views.xml',
        'wizard/export_historical_data_wizard_views.xml',
        'wizard/add_missing_emp_wizard_views.xml',

        # ============================== REPORT =============================
        # 'report/print_check.xml',
        'report/ach_report_templates.xml',

    ],
    'demo': [],
    'qweb': ['static/src/xml/*.xml'],
    'external_dependencies': {
        'python': ['ach'],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
}
