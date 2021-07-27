# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

{
    'name': 'Shipping Integration: Address Checker',
    'summary': 'Validate and auto correct delivery address using FedEx',
    'description': 'Validate and auto correct delivery address using FedEx',
    'version': '14.1.0.0',
    'category': 'Other',
    'author': 'Novobi LLC',
    'license': 'OPL-1',
    'website': 'https://www.novobi.com',
    'depends': ['omni_fedex'],
    'data': [
        # ============================== DATA =================================

        # ============================== SECURITY =============================
        'security/ir.model.access.csv',

        # ============================== VIEWS ================================
        'views/stock_picking_views.xml',

        # ============================== REPORT ===============================

        # ============================== WIZARD ===============================
        'wizard/address_validation_wizard_views.xml',

        # ============================== MENU =================================

    ],
    'qweb': ['static/src/xml/*.xml'],
    'installable': True,
    'auto_install': False,
    'application': False,
}

