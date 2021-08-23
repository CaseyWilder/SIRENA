from odoo import api, fields, models
from datetime import date
from dateutil.relativedelta import relativedelta


class DeductionEnrollmentPolicy(models.Model):
    _name = 'deduction.enrollment.policy'
    _description = 'Deduction Enrollment Policy'

    name = fields.Char('Name')
    deduction_id = fields.Many2one('payroll.deduction', string='Deduction')
    period = fields.Selection([('day', 'day(s)'), ('month', 'month(s)')], default='month')
    number = fields.Integer('Number')
    include_hiring_month = fields.Boolean('Include Hiring Month?', default=False)
    working_type = fields.Selection([('full', 'Full-time'), ('part', 'Part-time'), ('all', 'all')],
                                    string='Working Type', default='all')
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)

    eligible_employee_ids = fields.Many2many('hr.employee', string='Eligible Employees', compute='_compute_eligible_employee_ids')

    @api.depends('deduction_id', 'period', 'number', 'working_type')
    def _compute_eligible_employee_ids(self):
        Employee = self.env['hr.employee']
        for record in self:
            if record.deduction_id and record.period and record.working_type:
                domain = []
                if record.working_type != 'all':
                    domain.extend([('working_type', '=', record.working_type)])

                if record.period == 'day':
                    hire_date = date.today() - relativedelta(days=record.number)
                else:
                    hire_date = date.today() - relativedelta(months=record.number)

                domain.extend([('hire_date', '<=', hire_date)])

                ee_ids = Employee.search(domain).filtered(lambda x: record.deduction_id not in x.employee_deduction_ids.mapped('deduction_id'))

                record.eligible_employee_ids = [(6, 0, ee_ids.ids)]
            else:
                record.eligible_employee_ids = [(6, 0, [])]
