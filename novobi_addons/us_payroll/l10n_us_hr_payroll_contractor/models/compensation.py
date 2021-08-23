from odoo import api, fields, models, _


class PayslipCompensation(models.Model):
    _inherit = 'payslip.compensation'

    employee_type = fields.Selection(related='employee_id.employee_type', string="Employee Type", store=True)
