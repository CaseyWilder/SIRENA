from datetime import timedelta
from dateutil import relativedelta
import logging

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
from odoo.tools.float_utils import float_round
from ..utils.utils import get_default_date_format

_logger = logging.getLogger(__name__)


class PayFrequency(models.Model):
    _name = 'pay.frequency'
    _description = 'Pay Frequency'

    name = fields.Char('Name')
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    increment = fields.Integer('Increment', copy=False)
    frequency = fields.Selection([
        ('52', 'Weekly'),
        ('26', 'Bi-weekly'),
        ('24', 'Semi-monthly'),
        ('12', 'Monthly'),
    ], default='52', required=True, string='Frequency')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirm', 'Confirmed'),
        ('cancel', 'Canceled')
    ], default='draft', string='State', copy=False)

    first_pay_date = fields.Date('Pay Date #1', required=True)
    first_last_day_of_work = fields.Date('Last Day of Work #1', required=True)
    second_pay_date = fields.Date('Pay Date #2')
    second_last_day_of_work = fields.Date('Last Day of Work #2')
    deadline = fields.Integer('Submission Deadline', default=0)

    preview_area = fields.Html(compute='_compute_preview_area')
    pay_period_ids = fields.One2many('pay.period', 'pay_frequency_id', 'Periods', readonly=True)

    def name_get(self):
        result = []
        frequencies = dict(self._fields['frequency'].selection)
        for rec in self:
            result.append((rec.id, '{} - {}'.format(
                rec.name, frequencies.get(rec.frequency)
            )))
        return result

    ####################################################################################################################
    # CONSTRAINTS
    ####################################################################################################################
    @api.constrains('first_pay_date', 'first_last_day_of_work', 'second_pay_date', 'second_last_day_of_work', 'deadline')
    def _check_pay_period(self):
        for record in self:
            errors = record._get_error_check_pay_period()
            if errors:
                raise ValidationError(errors)

    ####################################################################################################################
    # ONCHANGE, COMPUTE/INVERSE
    ####################################################################################################################
    @api.onchange('first_pay_date', 'first_last_day_of_work', 'second_pay_date', 'second_last_day_of_work', 'deadline')
    def _onchange_pay_period(self):
        errors = self._get_error_check_pay_period()
        if errors:
            # This is a trick to bypass a js error in PAYROLL-490.
            # Seems like Html fields (or Char field with widget="html") must contain value, even "<br/>" still raises the error.
            self.preview_area = '<p class="d-none">Something went wrong!</p>'

            warning = {
                'title': _('Date Condition Error'),
                'message': errors,
            }
            return {'warning': warning}

    @api.depends(
        'frequency', 'increment', 'deadline',
        'first_pay_date', 'first_last_day_of_work',
        'second_pay_date', 'second_last_day_of_work'
    )
    def _compute_preview_area(self):
        self.preview_area = False
        for record in self:
            frequency = int(record.frequency)
            first_pay, first_work = record.first_pay_date, record.first_last_day_of_work
            second_pay, second_work = record.second_pay_date, record.second_last_day_of_work
            if first_pay and first_work and (
                    frequency in [52, 26, 12] or frequency == 24 and second_pay and second_work):
                record.preview_area = record.generate_preview_area()

    def generate_preview_area(self):
        self.ensure_one()
        return self._generate_preview_semi_monthly_area() if int(self.frequency) == 24 else \
            self._generate_preview_normal_area()

    def _generate_preview_normal_area(self):
        self.ensure_one()
        increment, limit = self.increment, self.increment + 4
        deadline = self.deadline
        table_template = """
            <p class="mt-3 mb-3"><u>Upcoming Pay Periods</u></p>
            <table class="table table-hover">
                <thead>
                    <tr>
                        <th>Period</th>
                        <th>Submission Deadline</th>
                        <th>Pay Date</th>
                    </tr>
                </thead>
                <tbody>
                    {rows}
                </tbody>
            </table>
         """
        rows = ""
        row_template = """
                        <tr>
                            <td>{period}</td>
                            <td>{submiss_date}</td>
                            <td>{pay_date}</td>
                        </tr>
                    """
        date_format = get_default_date_format(self)
        while increment < limit:
            start, end, pay_date = self.generate_period(increment)
            period = "{} &mdash; {}".format(start.strftime(date_format), end.strftime(date_format))
            submiss_date = pay_date - timedelta(days=min(deadline, (pay_date - end).days))
            rows += row_template.format(
                period=period,
                submiss_date=submiss_date.strftime(date_format),
                pay_date=pay_date.strftime(date_format))
            increment += 1

        return table_template.format(rows=rows)

    def _generate_preview_semi_monthly_area(self):
        self.ensure_one()
        increment, limit = self.increment, self.increment + 7
        deadline = self.deadline
        table_template = """
            <p>Upcoming Pay Periods:</p>
            <table class="table table-hover">
                <thead>
                    <tr>
                        <th style="border-right: 1px solid #dee2e6">Month</th>
                        <th>Period #1</th>
                        <th>Submission Deadline #1</th>
                        <th style="border-right: 1px solid #dee2e6">Pay Date #1</th>
                        <th>Period #2</th>
                        <th>Submission Deadline #2</th>
                        <th>Pay Date #2</th>
                    </tr>
                </thead>
                <tbody>
                    {rows}
                </tbody>
            </table>
         """
        row_template = """
                        <tr>
                            <td style="border-right: 1px solid #dee2e6">{month}</td>
                            <td>{period1}</td>
                            <td>{submiss_date1}</td>
                            <td style="border-right: 1px solid #dee2e6">{pay_date1}</td>
                            <td>{period2}</td>
                            <td>{submiss_date2}</td>
                            <td>{pay_date2}</td>
                        </tr>
                    """
        rows = ''

        # If (month of second_pay_date) > (month of first_pay_date)
        # -> first generated pay period (increment = 0) belongs to the SECOND period of its month.
        # Example: first_pay_date = 18.05.2019 and second_pay_date = 02.06.2019
        #       5:  ----------  -  18.05.2019
        #       6:  02.06.2019  -  18.06.2019
        date_format = get_default_date_format(self)
        if self.second_pay_date.month > self.first_pay_date.month and not increment % 2:
            start, end, pay_date = self.generate_period(increment)
            period = "{}  &mdash;  {}".format(start.strftime(date_format), end.strftime(date_format))
            submiss_date = pay_date - timedelta(days=min(deadline, (pay_date - end).days))
            month = pay_date.month
            rows = row_template.format(
                month=month,
                period1='', submiss_date1='', pay_date1='',
                period2=period, submiss_date2=submiss_date.strftime(date_format), pay_date2=pay_date.strftime(date_format)
            )
            increment += 1

        while increment < limit:
            start1, end1, pay_date1 = self.generate_period(increment)
            period1 = "{} &mdash; {}".format(start1.strftime(date_format), end1.strftime(date_format))
            submiss_date1 = pay_date1 - timedelta(days=min(deadline, (pay_date1 - end1).days))
            month = pay_date1.month
            increment += 1
            start2, end2, pay_date2 = self.generate_period(increment)
            period2 = "{} &mdash; {}".format(start2.strftime(date_format), end2.strftime(date_format))
            submiss_date2 = pay_date2 - timedelta(days=min(deadline, (pay_date2 - end2).days))
            increment += 1
            rows += row_template.format(
                month=month,
                period1=period1, submiss_date1=submiss_date1.strftime(date_format), pay_date1=pay_date1.strftime(date_format),
                period2=period2, submiss_date2=submiss_date2.strftime(date_format), pay_date2=pay_date2.strftime(date_format)
            )

        return table_template.format(rows=rows)

    ####################################################################################################################
    # ACTION
    ####################################################################################################################
    def button_confirm(self):
        self.ensure_one()
        # Check the link between cron and pay frequency
        self.state = 'confirm'
        return True

    def button_cancel(self):
        self.ensure_one()
        self.state = 'cancel'
        return True

    def button_set_to_draft(self):
        self.ensure_one()
        if self.state == 'confirm' and self.increment > 0:
            raise UserError(_('Cannot set to draft because some periods have been generated for this pay frequency!'))
        self.state = 'draft'
        return True

    def button_onboarding_confirm(self):
        self.ensure_one()
        self.button_confirm()
        company = self.env.company
        company.pay_frequency_id = self.id
        company.set_onboarding_step_done('us_payroll_onboarding_pay_frequency_state')
        return True

    ####################################################################################################################
    # CRON JOBS
    ####################################################################################################################
    @api.model
    def cron_generate_pay_period(self):
        _logger.info("===== START GENERATE PAY PERIOD =====")
        frequencies = self.search([('state', '=', 'confirm')])

        for frequency in frequencies:
            # Start generate pay period
            increment = frequency.increment
            start, end, pay_date = frequency.generate_period(increment)
            today = fields.Date.today()
            while end < today:
                frequency.generate_pay_period(start, end, pay_date, frequency)
                increment += 1
                start, end, pay_date = frequency.generate_period(increment)
            frequency.increment = increment

        _logger.info("===== END GENERATE PAY PERIOD =====")

    def generate_period(self, increment):
        self.ensure_one()
        """
        This function will be extended for specific project
        """
        frequency = int(self.frequency)
        first_work = self.first_last_day_of_work
        first_pay = self.first_pay_date

        # Weekly
        if frequency == 52:
            end = first_work + timedelta(weeks=increment)
            start = end - timedelta(days=6)
            pay_date = first_pay + timedelta(weeks=increment)

        # Bi-weekly
        elif frequency == 26:
            end = first_work + timedelta(weeks=increment*2)
            start = end - timedelta(days=13)
            pay_date = first_pay + timedelta(weeks=increment*2)

        # Semi-monthly
        elif frequency == 24:
            second_work = self.second_last_day_of_work
            _increment = int(float_round(value=increment/2, precision_digits=0, rounding_method='DOWN'))

            if increment % 2 == 0:
                start = second_work + relativedelta.relativedelta(months=_increment-1, days=1)
                end = first_work + relativedelta.relativedelta(months=_increment)
                pay_date = first_pay + relativedelta.relativedelta(months=_increment)
            else:
                start = first_work + relativedelta.relativedelta(months=_increment, days=1)
                end = second_work + relativedelta.relativedelta(months=_increment)
                pay_date = self.second_pay_date + relativedelta.relativedelta(months=_increment)

        # Monthly
        else:
            start = first_work + relativedelta.relativedelta(months=increment-1, days=1)
            end = first_work + relativedelta.relativedelta(months=increment)
            pay_date = first_pay + relativedelta.relativedelta(months=increment)

        return start, end, pay_date

    @api.model
    def generate_pay_period(self, start, end, pay_date, frequency):
        self.env['pay.period'].create({
            'pay_type': 'frequency',
            'start_date': start,
            'end_date': end,
            'pay_date': pay_date,
            'pay_frequency_id': frequency.id,
            'company_id': frequency.company_id.id,
        })

    ####################################################################################################################
    # HELPER METHODS
    ####################################################################################################################
    def _get_error_check_first_period(self):
        # Validate date condition for all periods
        error = ''
        first_pay, first_work = self.first_pay_date, self.first_last_day_of_work
        order = '#1' if int(self.frequency) == 24 else ''

        if first_pay and first_work:
            if first_pay < first_work:
                error += _('Pay Date {order} cannot be less than Last Day of Work {order}.\n'.format(order=order))
            elif self.deadline and (first_pay - first_work).days < self.deadline:
                error += _('Submission Deadline {order} must be between Pay Date {order} and Last Day of Work {order}\n'.format(order=order))
        return error

    def _get_error_check_second_period(self):
        # Validate date condition for semi-monthly periods
        if int(self.frequency) != 24:
            return ''

        error = ''
        first_pay, first_work = self.first_pay_date, self.first_last_day_of_work
        second_pay, second_work = self.second_pay_date, self.second_last_day_of_work
        min_days = 10
        max_days = 20

        if second_pay and second_work:
            if second_pay < second_work:
                error += _('Pay Date #2 cannot be less than Last Day of Work #2.\n')
            elif self.deadline and (second_pay - second_work).days < self.deadline:
                error += _('Submission Deadline #2 must be between Pay Date #2 and Last Day of Work #2.\n')

        if first_pay and second_pay and first_pay >= second_pay:
            error += _('Pay Date #2 must be greater than Pay Date #1.\n')

        if first_work and second_work:
            delta = (second_work - first_work).days
            if delta < min_days or delta > max_days:
                error += _('Last Day of Work #2 must be greater than Last Day of Work #1 from {} to {} days.\n'.format(min_days, max_days))
        return error

    def _get_error_check_pay_period(self):
        self.ensure_one()
        return self._get_error_check_first_period() + self._get_error_check_second_period()
