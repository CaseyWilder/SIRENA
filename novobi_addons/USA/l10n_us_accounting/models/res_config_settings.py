# -*- coding: utf-8 -*-

from odoo import fields, models, api


class ResConfigSettingsUSA(models.TransientModel):
    _inherit = 'res.config.settings'

    bad_debt_account_id = fields.Many2one("account.account", string='Write Off Account for Invoices',
                                          related='company_id.bad_debt_account_id', readonly=False,
                                          domain=[('deprecated', '=', False)])

    bill_bad_debt_account_id = fields.Many2one("account.account", string='Write Off Account for Bills',
                                          related='company_id.bill_bad_debt_account_id', readonly=False,
                                          domain=[('deprecated', '=', False)])

    report_1099_printing_margin_top = fields.Float(
        related='company_id.report_1099_printing_margin_top',
        string='Report 1099 Top Margin',
        readonly=False,
        help="Adjust the margins of generated 1099 report to make it fit your printer's settings."
    )

    report_1099_printing_margin_left = fields.Float(
        related='company_id.report_1099_printing_margin_left',
        string='Report 1099 Left Margin',
        readonly=False,
        help="Adjust the margins of generated 1099 report to make it fit your printer's settings."
    )

    # Bank Review screen settings
    bank_review_amount_filter = fields.Boolean(string='Amount Filter', related='company_id.bank_review_amount_filter',
                                               readonly=False)
    bank_review_date_filter = fields.Boolean(string='Date Filter', related='company_id.bank_review_date_filter',
                                             readonly=False)
    bank_review_transaction_type_filter = fields.Boolean(string='Transaction Type Filter', readonly=False,
                                                         related='company_id.bank_review_transaction_type_filter',)
