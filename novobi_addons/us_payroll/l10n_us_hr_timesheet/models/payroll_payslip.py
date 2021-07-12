from datetime import timedelta

from odoo import models, fields, api
from odoo.tools.float_utils import float_compare, float_round


class PayrollPayslip(models.Model):
    _inherit = 'payroll.payslip'

    timesheet_ids = fields.Many2many('account.analytic.line', compute='_compute_timesheet_ids_payslip', store=True, compute_sudo=True)

    @api.depends('start_date', 'end_date', 'employee_id.timesheet_ids', 'workweek_start', 'employee_type', 'checkin_method')
    def _compute_timesheet_ids_payslip(self):
        """
        Module project_timesheet_holidays will be installed if 'Record Time Off' is checked in Timesheet Settings.
        It will automatically generate new timesheet log when a leave request is approved, and remove that timesheet log
        if that leave request is refused.
        A timesheet log generated by this module will have field 'holiday_id', and can only be removed by refusing leave request.
        ---
        So, when calculating working hours using Timesheets, we must remove all timesheet log which having `holiday_id`
        """
        for record in self:
            timesheet_ids = False
            if (
                    record.employee_type != 'salary'
                    and record.start_date and record.end_date
                    and record.checkin_method == 'timesheet'
            ):
                start_date = record.start_date
                end_date = record.end_date

                if record.time_tracking_id :
                    workweek = int(record.time_tracking_id.workweek_start)
                    start = start_date.weekday()
                    start_date -= timedelta(days=start - workweek if start >= workweek else 7 + start - workweek)

                timesheet_ids = record.employee_id.timesheet_ids.filtered(lambda timesheet:
                                                                          not timesheet.holiday_id and
                                                                          start_date <= timesheet.date <= end_date)
            record.timesheet_ids = timesheet_ids

    def get_working_hours(self):
        self.ensure_one()
        if self.employee_type != 'salary' and self.checkin_method == 'timesheet':
            total, regular, overtime, double = self._get_working_hours_template('timesheet_ids', 'unit_amount')
            return {
                'worked_hours': float_round(total, precision_digits=2),
                'regular': float_round(regular, precision_digits=2),
                'overtime': float_round(overtime, precision_digits=2),
                'double_overtime': float_round(double, precision_digits=2)
            }
        return super().get_working_hours()

    def button_work_log_timesheet(self):
        self.ensure_one()
        if self.checkin_method == 'timesheet':
            view_id = self.env.ref('l10n_us_hr_timesheet.view_payroll_timesheet_grid_readonly')
            employee_id = self.employee_id
            start_date = self.start_date
            end_date = self.end_date

            return {
                'name': 'Timesheets - {}'.format(self.employee_id.name),
                'view_mode': 'grid',
                'res_model': 'account.analytic.line',
                'view_id': view_id.id,
                'domain': [
                    ('employee_id', '=', employee_id.id),
                    ('date', '>=', start_date),
                    ('date', '<=', end_date),
                    ('holiday_id', '=', False),
                ],
                'context': {
                    'grid_anchor': start_date.strftime('%Y-%m-%d'),
                },
                'type': 'ir.actions.act_window',
                'target': 'new'
            }