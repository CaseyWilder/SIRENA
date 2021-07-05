from odoo import models, fields, api

from ..utils.utils import convert_time_zone


class HrAttendance(models.Model):
    _inherit = 'hr.attendance'

    # Override to rename
    worked_hours = fields.Float(string='Working Hours', compute='_compute_worked_hours', store=True, readonly=True)

    date = fields.Date('Date', compute='_compute_date', store=True,
                       help='This field is to determine that an attendance belongs to an exact day and will be used to calculate working hours')

    @api.depends('check_in', 'employee_id')
    def _compute_date(self):
        tz = self.env.user.tz or 'UTC'

        for record in self:
            if record.employee_id and record.check_in:
                tz = record.employee_id.resource_calendar_id.tz or tz
                record.date = convert_time_zone(record.check_in, tz).date()
            else:
                record.date = False
