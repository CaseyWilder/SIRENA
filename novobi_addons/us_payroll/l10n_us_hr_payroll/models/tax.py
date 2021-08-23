from odoo import api, fields, models
from ..utils.utils import PAYABLE_CODE_PREFIX, EXPENSE_CODE_PREFIX, NO_DIGITS


class PayrollTax(models.Model):
    _name = 'payroll.tax'
    _description = 'Payroll Tax'
    _inherit = 'gl.account.mixin'
    _rec_name = 'label'

    name = fields.Char('Name')
    label = fields.Char('Label on paycheck')
    tax_id = fields.Char('Tax ID')
    geocode = fields.Char('GeoCode')
    school_dist = fields.Char('School District')
    is_er_tax = fields.Boolean('Is this a Company Tax?', default=False)

    ee_account_payable_id = fields.Many2one('account.account', 'Employee Account Payable', company_dependent=True)
    er_account_payable_id = fields.Many2one('account.account', 'Company Account Payable', company_dependent=True)
    er_expense_account_id = fields.Many2one('account.account', 'Company Expense Account', company_dependent=True)

    # Override
    gl_account_ids = fields.One2many('gl.account.line', 'tax_id', string='GL Account')

    def _create_payroll_account(self, vals):
        is_er_tax = vals.get('is_er_tax', False)
        name = vals.get('name', '')
        Account = self.env['account.account'].sudo()
        payable_account_type = self.env.ref('account.data_account_type_payable').id
        expense_account_type = self.env.ref('account.data_account_type_expenses').id

        company_id = vals.get('company_id', self.env.company.id)
        company = self.env['res.company'].sudo().browse(company_id)

        if is_er_tax:
            vals['er_account_payable_id'] = Account.create({
                'code': Account._search_new_account_code(company, NO_DIGITS, PAYABLE_CODE_PREFIX),
                'name': '{} Payable - Company'.format(name),
                'user_type_id': payable_account_type,
                'company_id': company.id,
                'reconcile': True
            }).id
            vals['er_expense_account_id'] = Account.create({
                'code': Account._search_new_account_code(company, NO_DIGITS, EXPENSE_CODE_PREFIX),
                'name': '{} Expense - Company'.format(name),
                'user_type_id': expense_account_type,
                'company_id': company.id,
            }).id

            # Create accounts when post JE
            if self:
                self.write({'er_account_payable_id': vals['er_account_payable_id'],
                            'er_expense_account_id': vals['er_expense_account_id']})
        else:
            vals['ee_account_payable_id'] = Account.create({
                'code': Account._search_new_account_code(company, NO_DIGITS, PAYABLE_CODE_PREFIX),
                'name': '{} Payable - Employee'.format(name),
                'user_type_id': payable_account_type,
                'company_id': company.id,
                'reconcile': True
            }).id

            # Create accounts when post JE
            if self:
                self.write({'ee_account_payable_id': vals['ee_account_payable_id']})

        return vals

    @api.model
    def create(self, vals):
        vals = self._create_payroll_account(vals)
        vals['label'] = vals.get('name', False)
        return super().create(vals)
