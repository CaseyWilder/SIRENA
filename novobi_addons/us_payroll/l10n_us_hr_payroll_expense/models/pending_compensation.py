from odoo import api, fields, models, _


class PendingCompensation(models.Model):
    _name = 'pending.compensation'
    _description = 'Pending Compensation'
    _rec_name = 'hr_expense_sheet_id'

    employee_id = fields.Many2one('hr.employee', string='Employee', required=True)
    employee_code = fields.Char(string='Employee ID', related='employee_id.employee_code')
    amount = fields.Monetary(string='Amount', require=True)
    currency_id = fields.Many2one('res.currency', string='Currency', default=lambda self: self.env.company.currency_id)
    hr_expense_sheet_id = fields.Many2one('hr.expense.sheet', string='Expense Report')
    payslip_compensation_ids = fields.One2many('payslip.compensation', 'linked_pending_compensation_id', string='Payslip Compensation')
    payslip_id = fields.Many2one('payroll.payslip', string='Payslip', related='payslip_compensation_ids.payslip_id')
    date = fields.Date(string='Date')
