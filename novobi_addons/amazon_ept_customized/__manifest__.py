# -*- coding: utf-8 -*-
{
    # App Information
    'name': 'Amazon Ept Customized by Novobi',
    'version': '14.0',
    'category': 'Sales',
    'summary': 'Amazon Ept Customized by Novobi',
    'website': 'https://novobi.com',
    'author': 'Novobi',
    # Dependencies
    'depends': ['amazon_ept', 'multiple_shipping_options'],

    # Views
    'data': [
        # ============================== DATA ===============================

        # ============================== MENU ===============================

        # ============================== WIZARDS ============================

        # ============================== VIEWS ==============================
        'views/product_views.xml',
        'views/sale_order_line_views.xml',
        'views/product_mapping_views.xml',
        'views/res_config_views.xml',
        # ============================== SECURITY ===========================
        'security/ir.model.access.csv',
        # ============================== TEMPLATES ==========================

        # ============================== REPORT =============================
    ],

    'installable': True,
    'auto_install': False,
    'application': False,
}
