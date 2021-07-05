from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.tools.float_utils import float_compare

from ..utils.utils import get_min_value, track_one2many

POLICY_SYNC_FIELDS = ['deduction_id', 'has_company_contribution',
                      'ee_amount_type', 'ee_post_amount_type',
                      'ee_amount', 'ee_max_amount_type', 'ee_max_amount', 'ee_maximum_period',
                      'er_amount_type', 'er_amount', 'maximum_amount', 'maximum_period']


class DeductionCategory(models.Model):
    _name = 'payroll.deduction.category'
    _description = 'Deduction Category'

    name = fields.Char('Name', required=True)
    vertex_id = fields.Char('Vertex ID', required=True)
    description = fields.Text('Vertex Description')
    has_company_contribution = fields.Boolean('Company Contribution?', default=False)


class DeductionType(models.Model):
    _name = 'payroll.deduction.type'
    _description = 'Deduction Type'

    name = fields.Char('Name', required=True)


class Deduction(models.Model):
    _name = 'payroll.deduction'
    _description = 'Deduction'

    def _get_type_id_domain(self):
        return [('id', 'in',
                 [self.env.ref('l10n_us_hr_payroll.payroll_deduction_type_other_deductions').id,
                  self.env.ref('l10n_us_hr_payroll.payroll_deduction_type_other_benefits').id])]

    name = fields.Char('Name')
    active = fields.Boolean('Active', default=True)
    type_id = fields.Many2one('payroll.deduction.type', 'Deduction Type', domain=_get_type_id_domain)
    category_id = fields.Many2one('payroll.deduction.category', 'Deduction Category')
    w2_code = fields.Char('W2 Box 12 Code')
    vertex_id = fields.Char('Vertex ID', related='category_id.vertex_id', store=True)
    description = fields.Text('Description', compute='_compute_description', store=True)
    ee_account_payable_id = fields.Many2one('account.account', 'Employee Account Payable', company_dependent=True)
    er_account_payable_id = fields.Many2one('account.account', 'Company Account Payable', company_dependent=True)
    er_expense_account_id = fields.Many2one('account.account', 'Company Expense Account', company_dependent=True)

    @api.depends('category_id', 'category_id.description')
    def _compute_description(self):
        for record in self:
            if record.category_id:
                record.description = record.category_id.description
            else:
                record.description = "This is a post-tax deduction."


class EmployeeDeduction(models.Model):
    _name = 'employee.deduction'
    _description = 'Deduction for Employee'
    _inherit = 'deduction.policy.template'
    _rec_name = 'employee_id'

    employee_id = fields.Many2one('hr.employee', 'Employee')
    deduction_policy_id = fields.Many2one('deduction.policy.template', 'Deduction Policy', ondelete="restrict")
    label = fields.Char('Label on paycheck')
    allowable_deduction_ids = fields.Many2many('payroll.deduction', string='Allowable Deductions',
                                               domain=[('vertex_id', '!=', False)])

    # For Maximum Type = Total Amount Owed
    payslip_ids = fields.One2many(related='employee_id.payslip_ids')
    payslip_deduction_ids = fields.One2many('payslip.deduction', 'employee_deduction_id', string='Payslip Deduction')
    owed_employee_remaining_amount = fields.Monetary('Employee Remaining Owed Amount',
                                                     compute='_compute_owed_employee_remaining_amount', store=True,
                                                     help='Current remaining amount after subtracting all amounts in "done" payslips')

    @api.depends('ee_max_amount_type', 'ee_max_amount', 'payslip_deduction_ids.state')
    def _compute_owed_employee_remaining_amount(self):
        """
        Compute Employee Remaining Owed Amount if pay period is set to 'done' or change 'ee_max_amount'
        """
        for record in self:
            if record.ee_max_amount_type == 'owed':
                total = sum(record.payslip_deduction_ids.filtered(lambda r: r.state == 'done').mapped('amount'))
                record.owed_employee_remaining_amount = record.ee_max_amount - total

    @api.constrains('employee_id', 'deduction_id')
    def _check_uniq_employee_deduction(self):
        for record in self:
            if any(line.deduction_id == record.deduction_id and line.id != record.id
                   for line in record.employee_id.employee_deduction_ids):
                raise ValidationError(_('Please make sure {} only has one deduction line per deduction.'.format(record.employee_id.name)))

    @api.constrains('ee_max_amount', 'ee_max_amount_type', 'ee_maximum_period')
    def _check_ee_max_amount(self):
        """
        Check maximum amount conditions.
        :raise ValidationError: if type is total amount owed and new maximum amount < paid amount
        :raise ValidationError: if type is fixed and new maximum amount < paid amount in this year
        """
        owed_deduction_ids = self.filtered(lambda r: r.ee_max_amount_type == 'owed')
        for record in owed_deduction_ids:
            paid_amount = sum(record.payslip_deduction_ids.mapped('amount'))
            if float_compare(paid_amount, record.ee_max_amount, precision_digits=2) == 1:
                raise ValidationError(_('Maximum Amount of "Total Amount Owed" type cannot be smaller than total amount'
                                        ' in all payslips generated.'))

        fixed_deduction_ids = self.filtered(lambda r: r.ee_max_amount_type == 'fixed' and r.ee_maximum_period == 'year')
        for record in fixed_deduction_ids:
            this_year = fields.Date.today().year
            paid_amount = sum(record.payslip_deduction_ids.filtered(lambda r: r.pay_date.year == this_year).mapped('amount'))
            if float_compare(paid_amount, record.ee_max_amount, precision_digits=2) == 1:
                raise ValidationError(_('Maximum Amount of "Fixed Amount" type cannot be smaller than total amount'
                                        ' in all payslips generated in this year.'))

    @api.onchange('deduction_policy_id')
    def _onchange_deduction_policy_id(self):
        policy_id = self.deduction_policy_id
        if policy_id:
            values = {}
            for field in POLICY_SYNC_FIELDS:
                values[field] = policy_id[field]
            self.update(values)

    @api.onchange('deduction_id')
    def _onchange_deduction_id(self):
        domain = []
        if self.deduction_id:
            domain.extend([('deduction_id.id', '=', self.deduction_id.id)])
            if not self.label:
                self.label = self.deduction_id.name
                # Deduction Policy has higher priority of Company Contribution
                if not self.deduction_policy_id:
                    self.has_company_contribution = self.deduction_id.category_id.has_company_contribution

        return {
            'domain': {'deduction_policy_id': domain},
        }

    def _from_id_to_name(self, model, id, return_obj=False):
        obj = self.env[model].browse(id) if id else False
        if return_obj:
            return obj
        return obj.name if obj else ''

    def _create_deduction_policy(self, vals):
        # Only create policy for Vertex deduction

        deduction = self._from_id_to_name('payroll.deduction', vals.get('deduction_id', False), return_obj=True)
        if not vals.get('deduction_policy_id', False) and self._name == 'employee.deduction' and deduction.vertex_id:
            employee_name = self._from_id_to_name('hr.employee', vals.get('employee_id', False))

            policy_vals = {'name': "{} - {}".format(deduction.name, employee_name)}
            for field in POLICY_SYNC_FIELDS:
                policy_vals[field] = vals[field]

            # Create Policy
            policy_id = self.env['deduction.policy.template'].sudo().create(policy_vals)
            vals['deduction_policy_id'] = policy_id.id
        return vals

    @api.model
    def create(self, values):
        if self._name == 'employee.deduction':
            values = self._create_deduction_policy(values)
        result = super().create(values)
        if self._name == 'employee.deduction':
            track_one2many("create", result)
        # Add deduction label if missing
        if not values.get('label', False):
            for record in result:
                record.label = record.deduction_id.name
        return result

    def write(self, values):
        if self._name == 'employee.deduction':
            track_one2many("update", self, values)
        return super(EmployeeDeduction, self).write(values)

    def unlink(self):
        if self._name == 'employee.deduction':
            track_one2many("remove", self)
        return super(EmployeeDeduction, self).unlink()


class PayslipDeduction(models.Model):
    _name = 'payslip.deduction'
    _inherit = ['employee.deduction', 'payslip.accumulated.amount']
    _order = 'pay_date'
    _description = 'Payslip Deduction Line'

    state = fields.Selection(related='payslip_id.state', store=True)
    is_history = fields.Boolean(related='payslip_id.is_history', store=True)
    is_regular = fields.Boolean('Is regular deduction?', default=False)
    amount = fields.Monetary('Employee Deduction in Dollar amount')
    er_dollar_amt = fields.Monetary('Company Contribution in Dollar amount')
    disposable_income = fields.Monetary('Disposable Income')

    # Accumulated Amount for Employer
    er_mtd_amount = fields.Monetary('Employer MTD', group_operator=None)
    er_qtd_amount = fields.Monetary('Employer QTD', group_operator=None)
    er_ytd_amount = fields.Monetary('Employer YTD', group_operator=None)

    # Override
    active = fields.Boolean('Active', default=True)
    employee_id = fields.Many2one('hr.employee', 'Employee', related='payslip_id.employee_id', store=True, readonly=False)

    # For Maximum Type = Total Amount Owed
    employee_deduction_id = fields.Many2one('employee.deduction', string='Employee Deduction')
    owed_payslip_remaining_amount = fields.Monetary('Payslip Remaining Owed Amount', group_operator=None,
                                                    help='Remaining amount of after subtracting all amounts in "done" payslips')

    def _calculate_owed_payslip_remaining_amount(self):
        """
        Calculate Payslip Remaining Owed Amount to find out the Amount of payslip before running payroll.
        """
        for record in self:
            if record.ee_max_amount_type == 'owed':
                emp_deduction_id = record.employee_deduction_id
                pay_deduction_ids = emp_deduction_id and emp_deduction_id.payslip_deduction_ids
                if pay_deduction_ids:
                    past_pay_deduction_ids = pay_deduction_ids.filtered(lambda r: r.payslip_id.state == 'done')
                    past_amount = sum(past_pay_deduction_ids.mapped('amount'))
                    record.owed_payslip_remaining_amount = record.ee_max_amount - past_amount

    # Monetary/Float fields must contain positive value
    _sql_constraints = [
        ('positive_deduction_amount', 'CHECK (amount >= 0)', _('Employee Deduction in Dollar amount must be positive.')),
        ('positive_deduction_er_dollar_amt', 'CHECK (er_dollar_amt >= 0)', _('Company Contribution in Dollar amount must be positive.')),
        ('positive_deduction_disposable_income', 'CHECK (disposable_income >= 0)', _('Disposable Income must be positive.')),
    ]

    # Override, we don't need to check duplication for payslip
    def _check_uniq_employee_deduction(self):
        return True

    # Override, we don't need to update has_company_contribution
    @api.onchange('deduction_id')
    def _onchange_deduction_id(self):
        domain = []
        if self.deduction_id:
            domain.extend([('deduction_id.id', '=', self.deduction_id.id)])
            if not self.label:
                self.label = self.deduction_id.name

        return {
            'domain': {'deduction_policy_id': domain},
        }

    def _get_disposable_income(self):
        for record in self:
            if not record.vertex_id and record.ee_post_amount_type == 'disposable':
                allowance_deductions = record.payslip_id.deduction_ids.filtered(lambda x: x.deduction_id.id in record.allowable_deduction_ids.ids)
                # PAYROLL-459: Exclude post-tax compensation when calculating post-tax deduction
                posttax_compensation_ids = record.payslip_id.compensation_ids.filtered('is_posttax')
                record.disposable_income = record.payslip_id.gross_pay - (sum(posttax_compensation_ids.mapped('amount')) +
                                                                          record.payslip_id.total_ee_tax +
                                                                          sum(allowance_deductions.mapped('amount')))

    def _get_deduction_dollar_amt(self):
        for record in self:
            if record.is_history:
                record.write({'amount': record.ee_amount, 'er_dollar_amt': record.er_amount})
                continue

            # Employee Amount
            ee_amount = 0
            if record.ee_amount_type == 'fixed' or record.ee_post_amount_type == 'fixed':
                ee_amount = record.ee_amount
            else:  # % of Gross, Net, Disposable
                base_amount = 0
                if record.ee_amount_type == 'percentage' or record.ee_post_amount_type == 'percentage':
                    base_amount = record.payslip_id.gross_pay_deduction
                elif record.ee_post_amount_type == 'net':
                    # PAYROLL-459: Exclude post-tax compensation when calculating post-tax deduction
                    posttax_compensation_ids = record.payslip_id.compensation_ids.filtered('is_posttax')
                    base_amount = record.payslip_id.net_pay - sum(posttax_compensation_ids.mapped('amount'))
                elif record.ee_post_amount_type == 'disposable':
                    base_amount = record.disposable_income
                ee_amount = (record.ee_amount * base_amount) / 100

            # Employee Maximum Amount
            if record.ee_max_amount_type and record.ee_max_amount:
                if record.ee_max_amount_type == 'fixed':
                    if record.ee_maximum_period == 'pay':
                        ee_amount = get_min_value(ee_amount, record.ee_max_amount)
                    elif record.ee_maximum_period == 'year':
                        # The YTD amount doesn't include this paycheck's amount.
                        if float_compare(record.ytd_amount + ee_amount, record.ee_max_amount, precision_digits=2) == 1:
                            ee_amount = record.ee_max_amount - record.ytd_amount
                elif record.ee_max_amount_type == 'percentage':
                    max_amount = (record.ee_max_amount * record.payslip_id.net_pay) / 100
                    ee_amount = get_min_value(ee_amount, max_amount)
                elif record.ee_max_amount_type == 'owed':
                    ee_amount = get_min_value(ee_amount, record.owed_payslip_remaining_amount)
                    record.owed_payslip_remaining_amount -= ee_amount

            # Employer Amount
            er_dollar_amt = record.er_amount
            if record.er_amount_type == 'percentage':
                er_dollar_amt = (record.er_amount * record.payslip_id.gross_pay_deduction) / 100
            elif record.er_amount_type == 'match':
                er_dollar_amt = (record.er_amount * ee_amount) / 100

            # Employer Maximum Amount
            if record.maximum_amount:
                if record.maximum_period == 'pay':
                    er_dollar_amt = get_min_value(er_dollar_amt, record.maximum_amount)
                elif record.maximum_period == 'year':
                    # The YTD amount doesn't include this paycheck's amount.
                    if float_compare(record.er_ytd_amount + er_dollar_amt, record.maximum_amount, precision_digits=2) == 1:
                        er_dollar_amt = record.maximum_amount - record.er_ytd_amount

            record.write({'amount': ee_amount, 'er_dollar_amt': er_dollar_amt})

    def _prepare_domain(self):
        domain = super(PayslipDeduction, self)._prepare_domain()
        deduction = self.deduction_id
        if deduction:
            domain += [('deduction_id', '=', deduction.id)]
        return domain

    def write_accumulated_amount(self, vals):
        """
        Inherit from payslip.accumulated.amount to change the fields to ER
        """
        if self.env.context.get('is_employer', False):
            self.write({
                'er_mtd_amount': vals.get('mtd_amount', 0),
                'er_qtd_amount': vals.get('qtd_amount', 0),
                'er_ytd_amount': vals.get('ytd_amount', 0)
            })
        else:
            super().write_accumulated_amount(vals)

    def calculate_accumulated_amount(self, amount='amount'):
        """
        Override from payslip_accumulated_amount.
        Users may create multiple deduction lines having same deduction types.
        Need to re-calculate their YTD amount
        """
        super(PayslipDeduction, self).calculate_accumulated_amount(amount)

        for i in range(len(self)):
            record = self[i]
            duplicate_ids = self[0:i].filtered(lambda r: r.deduction_id.id == record.deduction_id.id)

            if duplicate_ids:
                extra_amount = sum(duplicate_ids.mapped(amount))
                if amount == 'amount':
                    record.mtd_amount += extra_amount
                    record.qtd_amount += extra_amount
                    record.ytd_amount += extra_amount
                if amount == 'er_dollar_amt':
                    record.er_mtd_amount += extra_amount
                    record.er_qtd_amount += extra_amount
                    record.er_ytd_amount += extra_amount

    @api.model
    def create(self, vals):
        res = super(PayslipDeduction, self).create(vals)

        # In case this deduction belongs to historical payslip, add it to employee_deduction_ids in employee
        rec_ids = res.filtered(lambda r: r.is_history)
        for record in rec_ids:
            deduction_id = record.deduction_id.id
            employee_deduction_id = record.employee_id.employee_deduction_ids.filtered(lambda r: r.deduction_id.id == deduction_id)
            if len(employee_deduction_id) == 1:
                record.employee_deduction_id = employee_deduction_id.id
        return res
