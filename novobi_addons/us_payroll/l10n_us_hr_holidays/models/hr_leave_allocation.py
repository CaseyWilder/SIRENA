# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import datetime, time
from dateutil.relativedelta import relativedelta

from odoo import models, fields, api, _
from odoo.addons.resource.models.resource import HOURS_PER_DAY
from odoo.exceptions import ValidationError


class HolidaysAllocation(models.Model):
    _inherit = "hr.leave.allocation"

    number_of_hours_display = fields.Float(store=True, tracking=True)
    state_id = fields.Many2one('res.country.state', string='Related State', related='holiday_status_id.state_id', store=True)

    # Override to add semi-monthly and rename other options.
    interval_unit = fields.Selection(selection_add=[
        ('days', 'Daily'),
        ('weeks', 'Weekly'),
        ('semimonthly', 'Semi-monthly'),
        ('months', 'Monthly'),
        ('years', 'Yearly')
    ])
    nextcall = fields.Date(states={'draft': [('readonly', False)], 'confirm': [('readonly', False)]})
    semimonthly_start = fields.Integer('First Day', default=1, readonly=True,
                                       states={'draft': [('readonly', False)], 'confirm': [('readonly', False)]})
    semimonthly_end = fields.Integer('Second Day', default=15, readonly=True,
                                     states={'draft': [('readonly', False)], 'confirm': [('readonly', False)]})

    @api.constrains('interval_unit', 'semimonthly_start', 'semimonthly_end')
    def _check_semimonthly_accrual(self):
        for record in self.filtered(lambda r: r.interval_unit == 'semimonthly'):
            if not (record.semimonthly_start and record.semimonthly_end):
                raise ValidationError(_('First Day and Second Day are required to run accrual allocation by semi-monthly.'))
            if record.semimonthly_end <= record.semimonthly_start:
                raise ValidationError(_('Second Day must be greater than First Day.'))

    @api.depends('number_of_days', 'employee_id')
    def _compute_number_of_hours_display(self):
        for allocation in self:
            allocation.number_of_hours_display = allocation.number_of_days * (allocation.employee_id.sudo().resource_id.calendar_id.hours_per_day or HOURS_PER_DAY)

    def _prepare_holiday_values(self, employee):
        self.ensure_one()
        """
        Re-calculate number_of_days of employee's allocation
        """
        values = super()._prepare_holiday_values(employee=employee)
        emp_hours_per_day = employee.sudo().resource_id.calendar_id.hours_per_day
        values['number_of_days'] = (self.number_of_days * HOURS_PER_DAY) / emp_hours_per_day
        return values

    def update_immediate_accrual(self):
        self.ensure_one()
        self._update_accrual()
        return True

    @api.model
    def _update_accrual(self):
        """
        Method called by the cron task in order to increment the number_of_days when necessary.
        Override Odoo's method to add new case for Semi-monthly
        """
        today = fields.Date.from_string(fields.Date.today())

        holidays = self.search(
            [('allocation_type', '=', 'accrual'), ('employee_id.active', '=', True), ('state', '=', 'validate'),
             ('holiday_type', '=', 'employee'),
             '|', ('date_to', '=', False), ('date_to', '>', fields.Datetime.now()),
             '|', ('nextcall', '=', False), ('nextcall', '<=', today)])

        for holiday in holidays:
            values = {}

            delta = relativedelta(days=0)
            current_call = holiday.nextcall if holiday.nextcall else today

            # SEMI-MONTHLY
            if holiday.interval_unit == 'semimonthly':
                # Standardize first day and second day to remove invalid value
                first = max(holiday.semimonthly_start, 1)
                second = min(holiday.semimonthly_end, 31)

                # Next call will be the First Day
                if current_call.day < first:
                    next_call = current_call.replace(day=first)

                # Next call will be the Second Day.
                # For special cases, such as February and semimonthly_end = 30, this will raise a ValueError,
                # so we will set next call to the last day of current month
                elif first <= current_call.day < second:
                    try:
                        next_call = current_call.replace(day=second)
                    except ValueError:
                        next_call = current_call.replace(month=current_call.month + 1, day=1) - relativedelta(days=1)

                # Next call will be the First Day of next month
                else:
                    next_call = current_call.replace(month=current_call.month + 1, day=first)

                delta = next_call - current_call

            # Others
            else:
                if holiday.interval_unit == 'days':
                    delta = relativedelta(days=holiday.interval_number)
                if holiday.interval_unit == 'weeks':
                    delta = relativedelta(weeks=holiday.interval_number)
                if holiday.interval_unit == 'months':
                    delta = relativedelta(months=holiday.interval_number)
                if holiday.interval_unit == 'years':
                    delta = relativedelta(years=holiday.interval_number)
                next_call = current_call + delta

            values['nextcall'] = next_call

            period_start = datetime.combine(today, time(0, 0, 0)) - delta
            period_end = datetime.combine(today, time(0, 0, 0))

            # We have to check when the employee has been created
            # in order to not allocate him/her too much leaves
            start_date = holiday.employee_id._get_date_start_work()
            # If employee is created after the period, we cancel the computation
            if period_end <= start_date or period_end < holiday.date_from:
                holiday.write(values)
                continue

            # If employee created during the period, taking the date at which he has been created
            if period_start <= start_date:
                period_start = start_date

            employee = holiday.employee_id
            worked = employee._get_work_days_data_batch(
                period_start, period_end,
                domain=[('holiday_id.holiday_status_id.unpaid', '=', True), ('time_type', '=', 'leave')]
            )[employee.id]['days']
            left = employee._get_leave_days_data_batch(
                period_start, period_end,
                domain=[('holiday_id.holiday_status_id.unpaid', '=', True), ('time_type', '=', 'leave')]
            )[employee.id]['days']
            prorata = worked / (left + worked) if worked else 0

            days_to_give = holiday.number_per_interval
            if holiday.unit_per_interval == 'hours':
                # As we encode everything in days in the database we need to convert
                # the number of hours into days for this we use the
                # mean number of hours set on the employee's calendar
                days_to_give = days_to_give / (employee.resource_calendar_id.hours_per_day or HOURS_PER_DAY)

            values['number_of_days'] = holiday.number_of_days + days_to_give * prorata
            if holiday.accrual_limit > 0:
                values['number_of_days'] = min(values['number_of_days'], holiday.accrual_limit)

            holiday.write(values)
