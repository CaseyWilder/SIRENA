# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

{
    'name': 'Sirena UPS Capital Insurance',
    'summary': 'Implement UPS Capital Insurance integration for Sirena',
    'description': '',
    'version': '14.1.0.0',
    'category': 'Other',
    'author': 'Novobi LLC',
    "license": "OPL-1",
    'website': 'https://www.novobi.com',
    'depends': ['multiple_shipping_options', 'sirena_shipping'],
    'data': [
        # ============================== DATA =================================

        # ============================== SECURITY =============================

        # ============================== VIEWS ================================
        'views/stock_picking_views.xml',
        'views/shipping_account_views.xml',

        # ============================== REPORT ===============================

        # ============================== WIZARD ===============================

        # ============================== MENU =================================

    ],
    'qweb': ['static/src/xml/*.xml'],
    'installable': True,
    'auto_install': False,
    'application': False,
}
