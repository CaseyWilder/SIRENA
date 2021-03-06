# -*- coding: utf-8 -*-

from odoo import models, api, _, fields
from odoo.tools import float_compare

class BankReconciliationDifference(models.TransientModel):
    _name = 'account.bank.reconciliation.difference'
    _description = 'Bank Reconciliation Difference'

    company_id = fields.Many2one('res.company', string='Company', required=True,
                                 default=lambda self: self.env.user.company_id)
    adjustment_date = fields.Date('Adjustment Date', default=fields.Date.context_today)
    reconciliation_discrepancies_account_id = fields.Many2one('account.account',
                                                              string='Reconciliation Discrepancies Account',
                                                              related='company_id.reconciliation_discrepancies_account_id',
                                                              readonly=False)
    bank_reconciliation_data_id = fields.Many2one('account.bank.reconciliation.data')

    # -------------------------------------------------------------------------
    # HELPERS
    # -------------------------------------------------------------------------
    def _get_account_side(self, journal_id, difference):
        self.ensure_one()

        company_currency = self.env.company.currency_id
        debit_account = journal_id.default_account_id if float_compare(difference, 0,
                                                                       precision_rounding=company_currency.rounding) >= 0 \
            else self.reconciliation_discrepancies_account_id
        credit_account = self.reconciliation_discrepancies_account_id if float_compare(difference, 0,
                                                                                       precision_rounding=company_currency.rounding) >= 0 \
            else journal_id.default_account_id

        return debit_account, credit_account

    # -------------------------------------------------------------------------
    # BUSINESS METHODS
    # -------------------------------------------------------------------------
    def apply(self):
        self.ensure_one()

        # create journal entry
        difference = self.bank_reconciliation_data_id.difference
        journal_id = self.bank_reconciliation_data_id.journal_id
        company_currency = journal_id.company_id.currency_id
        currency = journal_id.currency_id or company_currency
        if currency != company_currency:
            # Convert difference into journal currency
            difference_in_currency = company_currency._convert(
                difference,
                currency,
                journal_id.company_id,
                self.adjustment_date or fields.Date.today()
            )
        else:
            difference_in_currency = difference

        debit_account, credit_account = self._get_account_side(journal_id, difference)

        new_account_move = self.env['account.move'].create({
            'journal_id': journal_id.id,
            'line_ids': [(0, 0, {
                    'account_id': debit_account.id,
                    'debit': abs(difference),
                    'credit': 0,
                    'amount_currency': abs(difference_in_currency),
                    'date': self.adjustment_date,
                    'name': 'Reconciliation Discrepancy',
                    'bank_reconciled': True,
                    'currency_id': currency.id
                }), (0, 0, {
                    'account_id': credit_account.id,
                    'debit': 0,
                    'credit': abs(difference),
                    'amount_currency': -abs(difference_in_currency),
                    'date': self.adjustment_date,
                    'name': 'Reconciliation Discrepancy',
                    'bank_reconciled': True,
                    'currency_id': currency.id
                })],
            'date': self.adjustment_date,
            'ref': 'Reconciliation Discrepancy',
        })
        self.bank_reconciliation_data_id.discrepancy_entry_id = new_account_move  # so we can reverse it when undo
        new_account_move.action_post()

        return self.bank_reconciliation_data_id.do_reconcile()
