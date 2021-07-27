# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

{
    'name': 'Sirena Purchase Customization',
    'summary': 'Modifies/Adds customization to purchase models for Sirena',
    'version': '14.1.0.0',
    'category': 'Other',
    'author': 'Novobi LLC',
    "license": "OPL-1",
    'website': 'https://www.novobi.com',
    'depends': ['purchase', 'sirena_product'],
    'data': [
        # ============================== DATA =================================
        'data/install_cn_font.xml',

        # ============================== SECURITY =============================

        # ============================== VIEWS ================================

        # ============================== REPORT ===============================
        'report/purchase_order_customization.xml',

        # ============================== WIZARD ===============================

        # ============================== MENU =================================

    ],
    'qweb': ['static/src/xml/*.xml'],
    'installable': True,
    'auto_install': False,
    'application': False,
}
