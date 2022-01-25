from odoo import fields, models, api
from odoo.tools.float_utils import float_compare


class AccountReconciliation(models.AbstractModel):
    _inherit = 'account.reconciliation.widget'

    # -------------------------------------------------------------------------
    # BANK STATEMENT
    # -------------------------------------------------------------------------
    @api.model
    def get_bank_statement_data(self, bank_statement_line_ids, srch_domain=[]):
        """
        Override.
        Called when load reviewed form.
        Add status = open to `domain` in order to remove excluded/reconciled bank statement lines.
        :param bank_statement_line_ids:
        :param srch_domain:
        :return:
        """
        srch_domain.append(('status', '=', 'open'))
        return super().get_bank_statement_data(bank_statement_line_ids, srch_domain)

    @api.model
    def process_bank_statement_line(self, st_line_ids, data):
        """
        Override.
        Called when clicking on button `Apply` on `bank_statement_reconciliation_view` (review screen)

        :param st_line_ids
        :param list of dicts data: must contains the keys
            'counterpart_aml_dicts', 'payment_aml_ids' and 'new_aml_dicts',
            whose value is the same as described in process_reconciliation
            except that ids are used instead of recordsets.
        :returns dict: used as a hook to add additional keys.
        """
        result = super().process_bank_statement_line(st_line_ids, data)

        statement_lines = self.env['account.bank.statement.line'].browse(st_line_ids)

        # Mark BSL as reviewed
        statement_lines.write({'status': 'confirm'})

        # Mark all the lines that are not Bank or Bank Suspense Account temporary_reconcile
        statement_lines.get_reconciliation_lines().write({'temporary_reconciled': True})

        return result

    # -------------------------------------------------------------------------
    # BATCH PAYMENT
    # -------------------------------------------------------------------------
    @api.model
    def get_move_lines_by_batch_payment(self, st_line_id, batch_payment_id):
        """
        Override
        Also get move lines for adjustments of batch payment.
        """
        res = super(AccountReconciliation, self).get_move_lines_by_batch_payment(st_line_id, batch_payment_id)
        st_line = self.env['account.bank.statement.line'].browse(st_line_id)
        batch_id = self.env['account.batch.payment'].browse(batch_payment_id)
        aml_ids = self.env['account.move.line']
        journal_accounts = [batch_id.journal_id.payment_debit_account_id.id, batch_id.journal_id.payment_credit_account_id.id]
        for line in batch_id.fund_line_ids:
            line_id = line.get_aml_adjustments(journal_accounts)
            aml_ids |= line_id
        aml_list = [self._prepare_js_reconciliation_widget_move_line(st_line, line) for line in aml_ids]

        return res + aml_list

    @api.model
    def get_batch_payments_data(self, bank_statement_ids):
        """
        Override
        Filter batch payments in BSL review screen following conditions:
        - Batch payments must have same Journal as BSL
        - Batch payments type (IN/OUT) must have Same Transaction Type as BSL
        - Unreconciled amount of batch payment <= amount of BSL
        """
        batch_payments = super(AccountReconciliation, self).get_batch_payments_data(bank_statement_ids)
        length = len(batch_payments)
        index = 0

        while index < length:
            batch = batch_payments[index]
            batch_id = self.env['account.batch.payment'].browse(batch['id'])
            move_lines = batch_id.get_batch_payment_aml()
            if move_lines:
                batch.update(batch_id._get_batch_info_for_review())
                index += 1
            else:
                del batch_payments[index]
                length -= 1

        return batch_payments

    # -------------------------------------------------------------------------
    # MATCHING CONDITION
    # -------------------------------------------------------------------------
    def _get_domain_for_transaction_filters(self, statement_line):
        """
        Helper: Get domain for amount, date and transaction type filters in bank review screen
        """
        domain = []
        company = statement_line.company_id or statement_line.journal_id.company_id
        is_negative_statement_line = statement_line.currency_id.compare_amounts(statement_line.amount, 0) < 0
        if company.bank_review_date_filter:
            domain += [('date', '<=', statement_line.date)]
        if company.bank_review_transaction_type_filter:
            if is_negative_statement_line:
                domain += [('debit', '=', 0)]
            else:
                domain += [('credit', '=', 0)]
        if company.bank_review_amount_filter:
            if is_negative_statement_line:
                domain += [('credit', '<=', -statement_line.amount), ('debit', '<=', -statement_line.amount)]
            else:
                domain += [('debit', '<=', statement_line.amount), ('credit', '<=', statement_line.amount)]

        return domain

    @api.model
    def _get_query_reconciliation_widget_customer_vendor_matching_lines(self, statement_line, domain=[]):
        """
        Override
        Add more conditions to filter account move lines of Customer/Vendor Matching tab in BSL review screen
        - Transaction Date <= BSL date
        - Based on transaction type (Deposit/Payment)
        - Transactions' amount <= BSLs' amount
        - Same Payee (OOTB)
        """
        domain = domain + self._get_domain_for_transaction_filters(statement_line)

        return super(AccountReconciliation, self)._get_query_reconciliation_widget_customer_vendor_matching_lines(statement_line, domain)

    @api.model
    def _get_query_reconciliation_widget_miscellaneous_matching_lines(self, statement_line, domain=[]):
        """
        Override
        Add more conditions to filter account move lines of Miscellaneous Matching tab in BSL review screen
        - Transaction Date <= BSL date
        - Based on transaction type (Deposit/Payment)
        - Transactions' amount <= BSLs' amount
        - Same Payee (OOTB)
        """
        liquidity_journals = self.env['account.journal'].search([('id', '!=', statement_line.journal_id.id),
                                                                 ('type', 'in', ['bank', 'cash'])])
        liquidity_account_ids = liquidity_journals.mapped('payment_credit_account_id.id') +\
                                liquidity_journals.mapped('payment_debit_account_id.id')
  
        domain = domain + [('account_id.id', 'not in', liquidity_account_ids)] \
                 + self._get_domain_for_transaction_filters(statement_line)

        return super(AccountReconciliation, self)._get_query_reconciliation_widget_miscellaneous_matching_lines(statement_line, domain)

    # -------------------------------------------------------------------------
    # HELPER AND PRIVATE
    # -------------------------------------------------------------------------
    @api.model
    def _get_trailing_query(self, statement_line, limit=None, offset=None):
        trailing_query, params = super()._get_trailing_query(statement_line, limit=limit, offset=offset)
        order_by_position = trailing_query.find('ORDER BY')
        offset_index = len('ORDER By') + 1
        sort_by_date_stmt = 'account_move_line.date DESC,'
        trailing_query_with_date_sorted = trailing_query[
                                          :order_by_position + offset_index] + sort_by_date_stmt + trailing_query[
                                                                                                   order_by_position + offset_index:]
        return trailing_query_with_date_sorted, params

    @api.model
    def _get_query_select_clause(self):
        select_clause = super()._get_query_select_clause()
        select_clause_with_date = select_clause + ",account_move_line.date"
        return select_clause_with_date