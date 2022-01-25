# -*- coding: utf-8 -*-

from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    bad_debt_account_id = fields.Many2one("account.account", string=' Write Off Account for Invoices',
                                          domain=[('deprecated', '=', False)])
    bill_bad_debt_account_id = fields.Many2one("account.account", string=' Write Off Account for Bills',
                                          domain=[('deprecated', '=', False)])
    reconciliation_discrepancies_account_id = fields.Many2one('account.account', 'Reconciliation Discrepancies Account',
                                                              domain=[('deprecated', '=', False)])
    report_1099_printing_margin_top = fields.Float(
        string='Report 1099 Top Margin',
        default=0.25,
        help="Adjust the margins of generated 1099 report to make it fit your printer's settings.",
    )
    report_1099_printing_margin_left = fields.Float(
        string='Report 1099 Left Margin',
        default=0.25,
        help="Adjust the margins of generated 1099 report to make it fit your printer's settings.",
    )

    # Bank Review screen settings
    bank_review_amount_filter = fields.Boolean(string='Amount Filter', default=True)
    bank_review_date_filter = fields.Boolean(string='Date Filter', default=True)
    bank_review_transaction_type_filter = fields.Boolean(string='Transaction Type Filter', default=True)
