# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'US Payroll: Holidays',
    'version': '14.0.1',
    'category': 'Other',
    'author': 'Novobi',
    'summary': """Manage public holidays for US Payroll""",
    'description': """Manage public holidays for US Payroll""",
    'website': 'https://www.novobi.com',
    'depends': [
        'base',
        # Enterprise
        'hr_holidays_gantt',

    ],
    'data': [
        # ============================== DATA =================================
        'data/ir_cron_data.xml',
        'data/ir_config_parameter_data.xml',


        # ============================== VIEWS ================================
        'views/hr_public_holidays_views.xml',
        'views/hr_leave_allocation_view.xml',
        'views/hr_leave_type_views.xml',
        'views/hr_leave_views.xml',
        'views/hr_holidays_gantt_view.xml',
        'views/assets.xml',

        # ============================== SECURITY =============================
        'security/ir.model.access.csv',

        # ============================== REPORT ===============================

        # ============================== WIZARD ===============================
        'wizard/genrate_holidays_wizard_views.xml',

        # ============================== MENU =================================
        'views/menuitem.xml',

    ],
    'demo': [],
    'qweb': [],
    'external_dependencies': {
        'python': ['holidays'],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
