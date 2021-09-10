# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

{
    'name': 'Sirena Multiple Shipping Options',
    'summary': 'Supports two FedEx shipping options',
    'description': 'Supports two FedEx shipping options',
    'version': '14.0.1.0.0',
    'category': 'Other',
    'author': 'Novobi LLC',
    "license": "OPL-1",
    'website': 'https://www.novobi.com',
    'depends': ['sirena_shipping', 'sirena_fedex', 'sirena_ups'],
    'data': [
        # ============================== DATA =================================

        # ============================== SECURITY =============================
        'security/ir.model.access.csv',

        # ============================== VIEWS ================================
        'views/stock_picking_views.xml',

        # ============================== REPORT ===============================

        # ============================== WIZARD ===============================
        'wizard/mso_void_label_views.xml',

        # ============================== MENU =================================

    ],
    'qweb': ['static/src/xml/*.xml'],
    'installable': True,
    'auto_install': False,
    'application': False,
}
