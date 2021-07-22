from odoo import api, fields, models, _


class ResCompany(models.Model):
    _inherit = 'res.company'

    expense_compensation_id = fields.Many2one('payroll.compensation', 'Expense Compensation')
