# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'US Payroll: Demo Data',
    'version': '14.0.1',
    'category': 'Other',
    'author': 'Novobi',
    'summary': """Initial demo data for US Payroll""",
    'description': """Initial demo data for US Payroll""",
    'website': 'https://www.novobi.com',
    'depends': ['l10n_us_hr_payroll'],
    'data': [
        'data/payroll_demo.xml',
    ],
    'demo': [
    ],
    'qweb': [],
    'installable': True,
    'application': False,
    'auto_install': False,
}
