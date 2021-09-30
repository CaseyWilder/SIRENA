# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

{
    'name': 'Sirena Barcode Customization',
    'summary': 'Customize Barcode settings to fit with Sirena picking process',
    'description': '',
    'version': '14.1.0.0',
    'category': 'Other',
    'author': 'Novobi LLC',
    "license": "OPL-1",
    'website': 'https://www.novobi.com',
    'depends': ['stock_barcode', 'sirena_shipping', 'multiple_shipping_options'],
    'data': [
        # ============================== DATA =================================

        # ============================== SECURITY =============================

        # ============================== VIEWS ================================
        'views/assets.xml',

        # ============================== REPORT ===============================

        # ============================== WIZARD ===============================

        # ============================== MENU =================================

    ],
    'qweb': ['static/src/xml/*.xml'],
    'installable': True,
    'auto_install': False,
    'application': False,
}
