from odoo import api, fields, models, _
from odoo.addons.l10n_us_hr_payroll.utils.utils import PAYABLE_CODE_PREFIX, EXPENSE_CODE_PREFIX, NO_DIGITS


class PayPeriod(models.Model):
    _inherit = 'pay.period'

    @api.model
    def generate_demo_data(self):
        Journal = self.env['account.journal'].sudo()
        Account = self.env['account.account'].sudo()
        current_company = self.env.company
        payable_account_type = self.env.ref('account.data_account_type_payable').id
        expense_account_type = self.env.ref('account.data_account_type_expenses').id

        # Account setting
        if not current_company.bank_account_id:
            bank_journal = Journal.search([('type', '=', 'bank'), ('company_id', '=', current_company.id)], limit=1)
            if not bank_journal:
                bank_journal = Journal.create({'name': 'Bank', 'type': 'bank', 'code': 'BAN'})
            current_company.bank_account_id = bank_journal.id

        if not current_company.payroll_expense_account_id:
            expense_account = Account.search([('name', '=', 'Salary Expenses'),
                                              ('company_id', '=', current_company.id)], limit=1)
            if not expense_account:
                expense_account = Account.create({
                    'code': Account._search_new_account_code(current_company, NO_DIGITS, EXPENSE_CODE_PREFIX),
                    'name': 'Payroll Expenses',
                    'user_type_id': expense_account_type,
                    'company_id': current_company.id
                })
            current_company.payroll_expense_account_id = expense_account.id

        # Account for Deduction
        pay_periods = self.search([('company_id', '=', current_company.id)], order='pay_date')
        deduction_ids = pay_periods.mapped('payslip_ids.deduction_ids.deduction_id')
        for deduction in deduction_ids:
            if not deduction.ee_account_payable_id:
                deduction.ee_account_payable_id = Account.create({
                    'code': Account._search_new_account_code(current_company, NO_DIGITS, PAYABLE_CODE_PREFIX),
                    'name': '{} Payable - Employee'.format(deduction.name),
                    'user_type_id': payable_account_type,
                    'company_id': current_company.id,
                    'reconcile': True
                }).id

            if deduction.vertex_id:
                if not deduction.er_expense_account_id:
                    deduction.er_expense_account_id = Account.create({
                        'code': Account._search_new_account_code(current_company, NO_DIGITS, EXPENSE_CODE_PREFIX),
                        'name': '{} Expense - Company'.format(deduction.name),
                        'user_type_id': expense_account_type,
                        'company_id': current_company.id,
                    }).id

                if not deduction.er_account_payable_id:
                    deduction.er_account_payable_id = Account.create({
                        'code': Account._search_new_account_code(current_company, NO_DIGITS, PAYABLE_CODE_PREFIX),
                        'name': '{} Payable - Company'.format(deduction.name),
                        'user_type_id': payable_account_type,
                        'company_id': current_company.id,
                        'reconcile': True
                    }).id

        # Confirm some pay periods
        # Net Pay might be negative in some cases then raises error, so we should put a try-except here
        if len(pay_periods) > 3:
            try:
                for i in range(3):
                    pay_periods[i].button_confirm()
                    pay_periods[i].button_done()
            except:
                pass
