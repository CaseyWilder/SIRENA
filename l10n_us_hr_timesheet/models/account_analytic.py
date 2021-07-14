from odoo import models, fields


class TimesheetLine(models.Model):
    _inherit = 'account.analytic.line'

    unit_amount = fields.Float(digits=(16, 2))
