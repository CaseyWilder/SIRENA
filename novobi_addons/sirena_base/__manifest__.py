# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

{
    'name': 'Sirena Base Module',
    'summary': 'Contains customized code for Sirena',
    'description': 'Contains customized code for Sirena',
    'version': '14.1.0.0',
    'category': 'Other',
    'author': 'Novobi LLC',
    'license': 'OPL-1',
    'website': 'https://www.novobi.com',
    'depends': ['contacts'],
    'data': [
        # ============================== DATA =================================
        'data/res_company_data.xml',
        'data/res_users_data.xml',

        # ============================== SECURITY =============================

        # ============================== VIEWS ================================

        # ============================== REPORT ===============================

        # ============================== WIZARD ===============================

        # ============================== MENU =================================

    ],
    'qweb': ['static/src/xml/*.xml'],
    'installable': True,
    'auto_install': False,
    'application': False,
}
