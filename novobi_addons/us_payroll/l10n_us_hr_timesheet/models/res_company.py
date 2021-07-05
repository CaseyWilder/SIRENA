from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    # Override
    checkin_method = fields.Selection(selection_add=[('timesheet', 'Timesheets')], ondelete={'timesheet': 'set default'})
