# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models
from odoo.addons.resource.models.resource import Intervals

from pytz import timezone
from datetime import datetime, time
from dateutil import rrule


class ResourceCalendar(models.Model):
    _inherit = 'resource.calendar'

    def _public_holidays_leave_intervals(self, start_dt, end_dt, employee_id, tz):
        """Get the public holidays for the current employee and given dates in
        the format expected by resource methods.

        :param: start_dt: Initial datetime.
        :param: end_dt: End datetime.
        :param: employee_id: Employee ID. It can be false.
        :return: List of tuples with (start_date, end_date) as elements.
        """
        HrHolidaysPublic = self.env['hr.public.holidays']
        leaves = []

        for day in rrule.rrule(rrule.YEARLY, dtstart=start_dt, until=end_dt):
            lines = HrHolidaysPublic.get_holidays_list(day.year, employee_id=employee_id)

            for line in lines:
                leaves.append((
                    datetime.combine(line.date, time.min).replace(tzinfo=tz),
                    datetime.combine(line.date, time.max).replace(tzinfo=tz),
                    line
                ))
        return Intervals(leaves)

    def _leave_intervals(self, start_dt, end_dt, resource=None, domain=None, tz=None):
        res = super()._leave_intervals(start_dt, end_dt, resource=resource, domain=domain, tz=tz)

        if self.env.context.get('exclude_public_holidays'):
            tz = tz or timezone((resource or self).tz)
            employee_id = self.env.context.get('employee_id', False)
            public_holidays = self._public_holidays_leave_intervals(start_dt, end_dt, employee_id, tz)
            res = res | public_holidays

        return res
