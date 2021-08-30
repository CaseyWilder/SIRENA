# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

{
    'name': 'Sirena Shipping Account Customization',
    'version': '14.0.1',
    'category': 'Other',
    'author': 'Novobi',
    "license": "OPL-1",
    'website': 'https://www.novobi.com',
    'depends': [
        'novobi_shipping_account'
    ],
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
