from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class TimeTrackingRule(models.Model):
    _name = 'time.tracking.rule'
    _description = 'Overtime Rule'

    name = fields.Char('Name', required=True)

    workweek_start = fields.Selection(
        [('0', 'Monday'), ('1', 'Tuesday'), ('2', 'Wednesday'), ('3', 'Thursday'),
         ('4', 'Friday'), ('5', 'Saturday'), ('6', 'Sunday')],
        string='Start of Workweek', default='6', required=True
    )

    weekly_ovt = fields.Integer('Weekly Overtime', default=40, required=True,
                                help='After working this many hours in a workweek, employees will be paid'
                                     'weekly overtime at 1.5x their regular hourly wage.')
    weekly_ovt_apply = fields.Boolean('Apply Weekly Overtime?', default=True, readonly=True)

    daily_ovt = fields.Integer('Daily Overtime', default=8,
                               help='After working this many hours in a workday, employees will be paid daily overtime'
                                    'at 1.5x their regular hourly wage.')
    daily_ovt_apply = fields.Boolean('Apply Daily Overtime?', default=False)

    daily_double_ovt = fields.Integer('Daily Double Overtime', default=12,
                                      help='After working this many hours in a workday, employees will be paid daily'
                                           'double overtime at 2x their regular hourly wage.')
    daily_double_ovt_apply = fields.Boolean('Apply Daily Double Overtime?', default=False)

    consecutive_7_days = fields.Boolean('7th Consecutive Day Overtime', default=False,
                                        help='In some states, overtime is earned at 1.5x an employee’s regular hourly'
                                             'wage on the 7th consecutive day of work in a workweek.')

    # Technical fields
    payslip_ids = fields.One2many('payroll.payslip', 'time_tracking_id', string='Payslip for Employee',
                                  domain=[('state', '!=', 'done'), ('start_date', '!=', False), ('end_date', '!=', False)],
                                  help='Store all payslips (in processed) using this Overtime rule')

    @api.constrains('weekly_ovt', 'weekly_ovt_apply', 'daily_ovt', 'daily_ovt_apply', 'daily_double_ovt', 'daily_double_ovt_apply')
    def _check_overtime_values(self):
        for record in self:
            errors = ''
            weekly, is_weekly = record.weekly_ovt, record.weekly_ovt_apply
            daily, is_daily = record.daily_ovt, record.daily_ovt_apply
            daily_double, is_daily_double = record.daily_double_ovt, record.daily_double_ovt_apply
            if is_weekly and not 40 <= weekly <= 168:
                errors += _('Weekly Overtime must be from 40 hours to 168 hours.\n')
            if is_daily and not 8 <= daily <= 12:
                errors += _('Daily Overtime must be from 8 hours to 12 hours.\n')
            if is_daily_double and daily_double != 12:
                errors += _('Daily Double Overtime must be 12 hours.\n')
            if is_daily and is_daily_double and daily >= daily_double:
                errors += _('Daily Double Overtime must be greater than Daily Overtime.\n')
            if errors:
                raise ValidationError(errors)

    def button_onboarding_confirm(self):
        self.ensure_one()
        company = self.env.company
        company.time_tracking_id = self.id
        company.set_onboarding_step_done('us_payroll_onboarding_time_tracking_state')
        return True
