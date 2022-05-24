# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class AccountChartTemplate(models.Model):
    _inherit = "account.chart.template"

    def _load(self, sale_tax_rate, purchase_tax_rate, company):
        """
        Run after install a new COA for the company.
        """
        res = super()._load(sale_tax_rate, purchase_tax_rate, company)

        company.set_stock_valuation_accounts()
        return res

