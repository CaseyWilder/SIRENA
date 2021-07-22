from odoo import api, fields, models, _



class PayslipDeduction(models.Model):
    _inherit = 'payslip.deduction'

    employee_type = fields.Selection(related='employee_id.employee_type', string="Employee Type", store=True)
