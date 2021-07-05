from odoo import api, fields, models, _
from ..utils.utils import _convert_value

DEDUCTION_SYNC_FIELDS = ['er_amount_type', 'er_amount']  # Normally we only sync 2 fields
DEDUCTION_ALL_SYNC_FIELDS = ['has_company_contribution', 'er_amount_type', 'er_amount',
                             'maximum_amount', 'maximum_period'] # Toggle has_company_contribution


class DeductionPolicyTemplate(models.Model):
    _name = 'deduction.policy.template'
    _description = 'Deduction Policy Template'

    name = fields.Char('Name')
    active = fields.Boolean('Active', default=True)
    currency_id = fields.Many2one('res.currency', string='Currency',
                                  default=lambda self: self.env.company.currency_id)
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    deduction_id = fields.Many2one('payroll.deduction', 'Deduction', ondelete='restrict', required=1)
    vertex_id = fields.Char('Vertex ID', related='deduction_id.vertex_id', store=True)
    employee_deduction_ids = fields.One2many('employee.deduction', 'deduction_policy_id', 'Employees')

    # Employee Deduction
    ee_amount_type = fields.Selection([
        ('fixed', 'Fixed Amount'),
        ('percentage', '% of Gross Pay')
    ], string='Employee Deduction Type', default='fixed')
    ee_post_amount_type = fields.Selection([
        ('fixed', 'Fixed Amount'),
        ('percentage', '% of Gross Pay'),
        ('net', '% of Net Pay'),
        ('disposable', '% of Disposable Income')
    ], string='Employee Post-Tax Deduction Type', default='fixed')
    ee_amount_type_label = fields.Char('Employee Deduction Type Label', compute='_compute_ee_amount_type_label', store=True)
    ee_amount = fields.Float('Employee Deduction Amount', digits=(16, 2), group_operator=None)
    ee_max_amount_type = fields.Selection([
        ('fixed', 'Fixed Amount'),
        ('percentage', '% of Net Pay per paycheck'),
        ('owed', 'Total Amount Owed')
    ], string="Employee Max Deduction Type")
    ee_max_amount = fields.Float('Employee Deduction Maximum Amount', digits=(16, 2), group_operator=None)
    ee_maximum_period = fields.Selection([('year', 'per Year'), ('pay', 'per Paycheck')],
                                         string='Employee Maximum Amount Period', default='year')

    # Company Contribution
    has_company_contribution = fields.Boolean('Company Contribution?')
    er_amount_type = fields.Selection([
        ('fixed', 'Fixed Amount'),
        ('percentage', '% of Gross Pay'),
        ('match', '% of Employee Deduction')
    ], string='Company Deduction Type', default='fixed')
    er_amount = fields.Float('Company Deduction Amount', digits=(16, 2), group_operator=None)
    maximum_amount = fields.Monetary('Company Deduction Maximum Amount', group_operator=None)
    maximum_period = fields.Selection([('year', 'per Year'), ('pay', 'per Paycheck')],
                                      string='Company Deduction Maximum Amount Period', default='year')

    # Monetary/Float fields must contain positive value
    _sql_constraints = [
        ('positive_deduction_ee_amount',      'CHECK (ee_amount >= 0)',       _('Employee Deduction Amount must be positive.')),
        ('positive_deduction_ee_max_amount',  'CHECK (ee_max_amount >= 0)',   _('Employee Deduction Max Amount must be positive.')),
        ('positive_deduction_er_amount',      'CHECK (er_amount >= 0)',       _('Company Deduction Amount must be positive.')),
        ('positive_deduction_maximum_amount', 'CHECK (maximum_amount >= 0)',  _('Company Deduction Maximum Amount must be positive.')),
    ]

    @api.onchange('deduction_id')
    def _onchange_deduction_id(self):
        if self.deduction_id:
            self.has_company_contribution = self.deduction_id.category_id.has_company_contribution

    @api.onchange('has_company_contribution')
    def _onchange_has_company_contribution(self):
        if not self.has_company_contribution:
            self.update({
                'er_amount_type': None,
                'er_amount': None,
                'maximum_amount': None,
                'maximum_period': None,
            })

    @api.onchange('ee_amount_type')
    def _onchange_ee_amount_type(self):
        if self.ee_amount_type:
            self.update({'ee_post_amount_type': None})

    @api.onchange('ee_post_amount_type')
    def _onchange_ee_post_amount_type(self):
        if self.ee_post_amount_type:
            self.update({'ee_amount_type': None})

    @api.depends('ee_amount_type', 'ee_post_amount_type')
    def _compute_ee_amount_type_label(self):
        for record in self:
            record.ee_amount_type_label = _convert_value(record, record.ee_amount_type, 'ee_amount_type') if record.ee_amount_type \
                else _convert_value(record, record.ee_post_amount_type, 'ee_post_amount_type')

    def sync_deduction_with_policy(self, vals):
        # Sync Policy with Employee Deduction
        if vals.get('has_company_contribution', -1) != -1:
            update_field = set(vals.keys()) & set(DEDUCTION_ALL_SYNC_FIELDS)
        else:
            update_field = set(vals.keys()) & set(DEDUCTION_SYNC_FIELDS)

        update_vals = {}
        if len(update_field) > 0:
            for field in update_field:
                update_vals[field] = vals[field]
            for record in self:
                record.employee_deduction_ids.write(update_vals)

    def write(self, vals):
        res = super().write(vals)
        if self._name == 'deduction.policy.template':
            self.sync_deduction_with_policy(vals)
        return res
