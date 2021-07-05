from odoo import models, fields, api


class Employee(models.Model):
    _inherit = 'hr.employee'

    # Store all timesheet records belong to this employee
    timesheet_ids = fields.One2many('account.analytic.line', 'employee_id', string='Payroll Timesheet')
