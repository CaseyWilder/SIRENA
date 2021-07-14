from odoo import api, fields, models, _


class PayslipTax(models.Model):
    _inherit = 'payslip.tax'

    employee_type = fields.Selection(related='employee_id.employee_type', string="Employee Type", store=True)
