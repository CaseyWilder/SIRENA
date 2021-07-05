from odoo import models, fields


class PayslipMixin(models.AbstractModel):
    _inherit = 'payslip.mixin'

    # Override
    checkin_method = fields.Selection(selection_add=[('timesheet', 'Timesheets')], ondelete={'timesheet': 'set default'})
