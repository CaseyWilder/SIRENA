# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

{
    'name': 'Novobi US Accounting Installation',
    'summary': 'Install all modules of Novobi US Accounting',
    'author': 'Novobi',
    'website': 'http://www.odoo-accounting.com',
    'category': 'Accounting',
    'version': '14.0',
    'license': 'OPL-1',
    'depends': [
        'account_billable_expense_cancel',
        'purchase_billable_expense',
        'account_budget_spreadsheet',
        'account_partner_deposit_us_accounting',
        'purchase_partner_deposit',
        'sale_partner_deposit',
        'cash_flow_projection_deposit',
        'l10n_us_stock_account',
        'novobi_account_tax',
        'novobi_audit_trail',
        'novobi_recurring_transactions',
    ],
    'qweb': ['static/src/xml/*.xml'],
    'application': False,
    'installable': True,
}
