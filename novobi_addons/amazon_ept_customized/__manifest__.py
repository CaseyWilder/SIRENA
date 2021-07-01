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
    'depends': ['amazon_ept'],

    # Views
    'data': [
        # ============================== DATA ===============================

        # ============================== MENU ===============================

        # ============================== WIZARDS ============================

        # ============================== VIEWS ==============================
        'views/product_views.xml',
        # ============================== SECURITY ===========================

        # ============================== TEMPLATES ==========================

        # ============================== REPORT =============================
    ],

    'installable': True,
    'auto_install': False,
    'application': False,
}
