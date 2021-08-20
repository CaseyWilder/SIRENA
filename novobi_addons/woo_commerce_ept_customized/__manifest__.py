# -*- coding: utf-8 -*-
{
    # App Information
    'name': 'Woo Commerce Ept Customized by Novobi',
    'version': '14.0',
    'category': 'Sales',
    'summary': 'Woo Commerce Ept Customized by Novobi',
    'website': 'https://novobi.com',
    'author': 'Novobi',
    # Dependencies
    'depends': ['woo_commerce_ept'],

    # Views
    'data': [
        # ============================== DATA ===============================

        # ============================== MENU ===============================

        # ============================== WIZARDS ============================

        # ============================== VIEWS ==============================
        'views/product_mapping_views.xml',
        # ============================== SECURITY ===========================
        'security/ir.model.access.csv',
        # ============================== TEMPLATES ==========================

        # ============================== REPORT =============================
    ],

    'installable': True,
    'auto_install': False,
    'application': False,
}
