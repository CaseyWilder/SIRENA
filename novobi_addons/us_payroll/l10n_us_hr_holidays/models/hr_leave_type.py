# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models, _
from odoo.exceptions import UserError


class HrLeaveType(models.Model):
    _inherit = 'hr.leave.type'
    _order = 'sequence'

    exclude_public_holidays = fields.Boolean(string='Exclude Public Holidays', default=True,
                                             help="If enabled, public holidays are skipped in leave days (It doesn't support for leave hours) calculation.")
    public_holiday_id = fields.Many2one('hr.public.holidays', string='Public Holidays')
    state_id = fields.Many2one('res.country.state', string='Related State', related='public_holiday_id.state_id', store=True)

    def get_public_holiday_leave_type(self, public_holiday_id):
        leave_type = self.search([('public_holiday_id', '=', public_holiday_id)], limit=1)
        if not leave_type:
            raise UserError(_('Cannot find Leave Type for this public holidays!'))

        return leave_type
