from odoo import api, fields, models


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    is_payroll_bank_account = fields.Boolean(compute='_compute_is_payroll_bank_account')

    @api.depends_context('is_payroll_bank_account')
    @api.depends('company_id.bank_account_id')
    def _compute_is_payroll_bank_account(self):
        is_payroll_bank_account = self._context.get('is_payroll_bank_account', False)
        for record in self:
            record.is_payroll_bank_account = is_payroll_bank_account or (record.company_id and (record == record.company_id.bank_account_id))
