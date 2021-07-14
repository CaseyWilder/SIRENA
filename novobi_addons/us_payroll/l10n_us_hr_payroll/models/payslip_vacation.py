# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class PayslipVacation(models.Model):
    _name = 'payslip.vacation'
    _description = 'Vacation for each payslip'

    payslip_id = fields.Many2one('payroll.payslip', 'Payslip')
    leave_type_id = fields.Many2one('hr.leave.type', string='Leave Type')
    payroll_compensation_id = fields.Many2one('payroll.compensation', 'Compensation Type')
    remaining_leave_days = fields.Float(string='Balance (Days)', digits=(16, 2))
    remaining_leave_hours = fields.Float(string='Balance (Hours)', digits=(16, 2))
    number_of_days = fields.Float(string='Days used in this paycheck', digits=(16, 2))
    number_of_hours = fields.Float(string='Hours used in this paycheck', digits=(16, 2))
    company_id = fields.Many2one('res.company', related='payslip_id.company_id', readonly=True, store=True)
