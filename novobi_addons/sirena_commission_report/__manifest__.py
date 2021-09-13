# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

{
    'name': 'Sirena Commission Report',
    'summary': 'Sirena Commission Report',
    'description': 'Sirena Commission Report',
    'version': '14.1.0.0',
    'category': 'Other',
    'author': 'Novobi LLC',
    "license": "OPL-1",
    'website': 'https://www.novobi.com',
    'depends': ['sale', 'amazon_ept'],
    'data': [
        # ============================== DATA =================================

        # ============================== SECURITY =============================
        'security/ir.model.access.csv',
        # ============================== VIEWS ================================
        'views/commission_list_views.xml',
        'views/commission_report_views.xml',
        # ============================== REPORT ===============================

        # ============================== WIZARD ===============================
        'wizard/generate_commission_report_wizard_views.xml',
        # ============================== MENU =================================
        'views/menuitem.xml'
    ],
    'qweb': ['static/src/xml/*.xml'],
    'installable': True,
    'auto_install': False,
    'application': False,
}
