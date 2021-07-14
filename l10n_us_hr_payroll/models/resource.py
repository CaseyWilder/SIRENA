from collections import defaultdict
from datetime import timedelta

from odoo import fields, models, api, _
from odoo.tools import float_utils
from odoo.addons.resource.models.resource import ROUNDING_FACTOR

from ..utils.utils import convert_time_zone


class ResourceMixin(models.AbstractModel):
    _inherit = "resource.mixin"

    # Override to change field name
    resource_calendar_id = fields.Many2one(string='Working Schedule')


class ResourceCalendar(models.Model):
    _inherit = 'resource.calendar'

    hours_per_week = fields.Float("Total hours per week", digits=(16, 2), compute='_compute_hours_per_week', store=True,
                                  help="Total hours per week a resource is supposed to work with this calendar.")

    # Technical fields
    payslip_ids = fields.One2many('payroll.payslip', 'resource_calendar_id', string='Payslip for Employee',
                                  domain=[('state', '!=', 'done'), ('start_date', '!=', False), ('end_date', '!=', False)],
                                  help='Store all payslips (in processed) using this working hours')
    employee_ids = fields.One2many('hr.employee', 'resource_calendar_id', string='Employees', help='Store all employees using this working hours')
    outdated_holiday_leaves = fields.Boolean('Holiday Leaves Outdated', default=False, help='Technical fields for handling public holiday leaves')

    def _calculate_hours_per_week(self):
        self.ensure_one()
        attendances = self.attendance_ids.filtered(lambda r: not r.date_from and not r.date_to)
        hour_count = 0.0
        for attendance in attendances:
            hour_count += attendance.hour_to - attendance.hour_from
        return hour_count

    @api.depends('attendance_ids')
    def _compute_hours_per_week(self):
        for record in self:
            record.hours_per_week = record._calculate_hours_per_week()

    def get_work_days_data(self, from_datetime, to_datetime, compute_leaves=True, domain=None):
        """
        Copy function from resource.mixin, use timezone of this resource calendar
        """
        self.ensure_one()
        tz = self.tz
        from_datetime = convert_time_zone(from_datetime, tz)
        to_datetime = convert_time_zone(to_datetime, tz)

        from_full = from_datetime - timedelta(days=1)
        to_full = to_datetime + timedelta(days=1)
        intervals = self._attendance_intervals(from_full, to_full)
        day_total = defaultdict(float)
        for start, stop, meta in intervals:
            day_total[start.date()] += (stop - start).total_seconds() / 3600

        # actual hours per day
        if compute_leaves:
            intervals = self._work_intervals(from_datetime, to_datetime, domain=domain)
        else:
            intervals = self._attendance_intervals(from_datetime, to_datetime)
        day_hours = defaultdict(float)
        for start, stop, meta in intervals:
            day_hours[start.date()] += (stop - start).total_seconds() / 3600

        # compute number of days as quarters
        days = sum(
            float_utils.round(ROUNDING_FACTOR * day_hours[day] / day_total[day]) / ROUNDING_FACTOR
            for day in day_hours
        )
        return {
            'days': days,
            'hours': sum(day_hours.values()),
        }

    def button_see_employees(self):
        self.ensure_one()
        return {
            'name': _('Employee'),
            'type': 'ir.actions.act_window',
            'view_mode': 'kanban,tree,form',
            'res_model': 'hr.employee',
            'domain': [('id', 'in', self.employee_ids.ids)],
            'target': 'current',
        }

    def button_generate_holiday_leave(self):
        """
        Regenerate holiday leave requests for all employees using this resource calendar in case it is changed.
        """
        self.ensure_one()
        if self.outdated_holiday_leaves:
            for employee in self.employee_ids:
                employee.button_generate_holiday_leave()
            self.outdated_holiday_leaves = False

    def write(self, values):
        # If Working Times or Time zones is changed, raise outdated holidays on Calendar and Employee
        if 'attendance_ids' in values or 'tz' in values:
            self.mapped('employee_ids').write({'outdated_holiday_leaves': True})
            self.write({'outdated_holiday_leaves': True})

        return super(ResourceCalendar, self).write(values)
