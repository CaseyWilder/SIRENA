# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

{
    'name': 'Shipping Account',
    'version': '13.0.1.0.0',
    'category': 'Other',
    'author': 'Novobi',
    "license": "OPL-1",
    'website': 'https://www.novobi.com',
    'depends': [
        'delivery',
        'web_widget_selection_group'
    ],
    'data': [
        'data/ir_cron_data.xml',
        'data/report_paperformat_data.xml',
        'data/test_connection_data.xml',

        'security/ir.model.access.csv',

        'views/stock_report_views.xml',

        'views/assets.xml',
        'views/stock_picking_package_views.xml',
        'views/stock_report_views.xml',
        'views/stock_picking_views.xml',
        'views/shipping_method_channel_views.xml',
        'views/res_config_settings_views.xml',
        'views/delivery_view.xml',
        'views/report_packing_slip.xml',
        'views/product_packaging_views.xml',
        'views/shipping_account_views.xml',

        'wizard/confirm_create_shipping_label.xml',
        'wizard/update_done_quantities_views.xml',
    ],
    'qweb': ['static/src/xml/*.xml'],
    'installable': True,
    'auto_install': False,
    'application': True,
}