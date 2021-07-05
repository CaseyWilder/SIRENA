from odoo import api, fields, models, _
from ..utils.utils import track_one2many


class CompensationCategory(models.Model):
    _name = 'payroll.compensation.category'
    _description = 'Compensation Category'

    name = fields.Char('Name', required=1)
    vertex_id = fields.Char('Vertex ID', required=1)
    description = fields.Text('Vertex Description')
    incl_gp_deduction = fields.Boolean('Is this compensation included in gross pay for deduction?', default=False)


class Compensation(models.Model):
    _name = 'payroll.compensation'
    _description = 'Compensation'
    _inherit = 'gl.account.mixin'

    name = fields.Char('Name')
    category_id = fields.Many2one('payroll.compensation.category', 'Compensation Category',
                                  compute='_compute_category_id', store=True)
    description = fields.Text('Description', compute='_compute_category_id', store=True)
    vertex_id = fields.Char('Vertex ID', related='category_id.vertex_id', store=True)
    incl_gp_deduction = fields.Boolean(related='category_id.incl_gp_deduction')
    active = fields.Boolean('Active', default=True)
    account_receivable_id = fields.Many2one('account.account', 'Account Receivable', company_dependent=True)
    w2_code = fields.Char('W2 Box 12 Code')
    is_posttax = fields.Boolean('Post-tax Compensation?', default=False)

    @api.depends('is_posttax', 'category_id')
    def _compute_category_id(self):
        """
        Remove Compensation Category if this is a post-tax compensation (PAYROLL-461),
        otherwise will keep the old value, or assign the default category (Cash) if it is not set.
        :return:
        """
        default_comp = self.env.ref('l10n_us_hr_payroll.payroll_compensation_category_0', raise_if_not_found=False) or self.env['payroll.compensation']
        for record in self:
            if record.is_posttax:
                record.category_id = False
                record.description = 'This is a post-tax compensation'
            else:
                record.category_id = record.category_id or default_comp
                record.description = record.category_id.description


class EmployeeCompensation(models.Model):
    _name = 'employee.compensation'
    _description = 'Compensation for Employee'
    _rec_name = 'compensation_id'

    compensation_id = fields.Many2one('payroll.compensation', 'Compensation', ondelete='restrict', required=1)
    employee_id = fields.Many2one('hr.employee', 'Employee')
    vertex_id = fields.Char('Vertex ID', related='compensation_id.vertex_id', store=True)
    incl_gp_deduction = fields.Boolean(related='compensation_id.incl_gp_deduction')
    label = fields.Char('Label on paycheck')
    amount = fields.Monetary('Amount')
    company_id = fields.Many2one('res.company', related='employee_id.company_id', readonly=True, store=True)
    currency_id = fields.Many2one('res.currency', related='employee_id.currency_id', readonly=True, store=True)
    active = fields.Boolean('Active', related='compensation_id.active')
    is_posttax = fields.Boolean(related='compensation_id.is_posttax', readonly=True, store=True)

    # Monetary/Float fields must contain positive value
    _sql_constraints = [
        ('positive_compensation_amount', 'CHECK (amount >= 0)', _('Amount must be positive.')),
    ]

    @api.onchange('compensation_id')
    def _onchange_compensation_id(self):
        if self.compensation_id and not self.label:
            self.label = self.compensation_id.name

    @api.model
    def create(self, values):
        result = super(EmployeeCompensation, self).create(values)
        # Add compensation label if missing
        if not values.get('label', False):
            for record in result:
                record.label = record.compensation_id.name
        if self._name == 'employee.compensation':
            track_one2many("create", result)
        return result

    def write(self, values):
        if self._name == 'employee.compensation':
            track_one2many("update", self, values)
        return super(EmployeeCompensation, self).write(values)

    def unlink(self):
        if self._name == 'employee.compensation':
            track_one2many("remove", self)
        return super(EmployeeCompensation, self).unlink()


class PayslipCompensation(models.Model):
    _name = 'payslip.compensation'
    _inherit = ['employee.compensation', 'payslip.accumulated.amount']
    _description = 'Payslip Compensation Line'

    is_regular = fields.Boolean('Is regular compensation?', default=False)
    sequence = fields.Integer('Sequence', default=10)

    # Special flag for salary, vacation, sick...
    is_salary = fields.Boolean('Is Salary line?', default=False)
    rate = fields.Monetary('Rate')
    hours = fields.Float('Hours', digits=(16, 2))

    # Monetary/Float fields must contain positive value
    _sql_constraints = [
        ('positive_compensation_rate',  'CHECK (rate >= 0)',    _('Rate must be positive.')),
        ('positive_compensation_hours', 'CHECK (hours >= 0)',   _('Hours must be positive.')),
    ]

    # Override
    active = fields.Boolean('Active', related=False, default=True)

    def calculate_accumulated_amount(self, amount='amount'):
        """
        Override from payslip_accumulated_amount.
        payroll_payslip._update_compensation_list() will create compensations with higher priority, such as Salary,
        Overtime Pay, Double Overtime Pay, Holiday Pay, Sick Pay ... (1) and may have same compensation types with
        current compensations copied from Employee (2).
        (1) and (2) have the same initial accumulated amount => Wrong MTD/QTD/YTD of (2).

        To add amount of (1) into MTD/QTD/YTD of (2) if they have same compensation type.
        """
        super(PayslipCompensation, self).calculate_accumulated_amount(amount)

        # Compensations created by confirming period (salary lines).
        post_ids = self.filtered('is_salary')
        # Compensations added manually in payslip.
        pre_ids = self - post_ids

        for i in range(len(pre_ids)):
            record = pre_ids[i]
            duplicate_ids = (post_ids + pre_ids[0:i]).filtered(lambda r: r.compensation_id.id == record.compensation_id.id)

            if duplicate_ids:
                extra_amount = sum(duplicate_ids.mapped(amount))
                record.mtd_amount += extra_amount
                record.qtd_amount += extra_amount
                record.ytd_amount += extra_amount

    def _prepare_domain(self):
        domain = super(PayslipCompensation, self)._prepare_domain()
        compensation = self.compensation_id
        if compensation:
            domain += [('compensation_id', '=', compensation.id)]
        return domain
