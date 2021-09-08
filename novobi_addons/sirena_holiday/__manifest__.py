# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

{
    'name': 'Sirena Public Holidays',
    'summary': 'Customize Novobi US Public Holidays',
    'description': 'Customize Novobi US Public Holidays',
    'version': '14.1.0.0',
    'category': 'Other',
    'author': 'Novobi LLC',
    "license": "OPL-1",
    'website': 'https://www.novobi.com',
    'depends': ['l10n_us_hr_holidays'],
    'data': [
        # ============================== DATA =================================
        'data/init_public_holidays.xml',

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
