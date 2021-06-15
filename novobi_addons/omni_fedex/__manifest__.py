# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

{
    'name': 'FedEx Shipping Account',
    'version': '13.0.1.0.0',
    'category': 'Other',
    'author': 'Novobi',
    "license": "OPL-1",
    'website': 'https://www.novobi.com',
    'depends': [
        'delivery_fedex', 'novobi_shipping_account'
    ],
    'data': [
        'data/delivery_carrier_data.xml',
        'data/delivery_fedex.xml',
        'views/shipping_account_views.xml',
        'views/stock_picking_views.xml'
    ],
    'qweb': ['static/src/xml/*.xml'],
    'installable': True,
    'auto_install': False,
    'application': True,
}
