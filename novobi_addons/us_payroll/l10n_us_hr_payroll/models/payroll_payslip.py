import json
from datetime import datetime, time, timedelta

from odoo import api, fields, models, _
from odoo.tools.float_utils import float_compare, float_round
from odoo.exceptions import UserError, ValidationError

from ..utils.utils import get_default_date_format
from ..utils.vertex import Vertex
from ..utils.time_tracking import get_all_working_hours

WORKING_DAYS_IN_YEAR = 260

SALARY_TYPE = {
    'regular': 'l10n_us_hr_payroll.payroll_compensation_salary',
    'overtime': 'l10n_us_hr_payroll.payroll_compensation_ot',
    'double': 'l10n_us_hr_payroll.payroll_compensation_dot'
}

# Compensation list should be sorted by priority: Salary, Regular Pay, Overtime Pay, Double Overtime Pay....
SEQUENCE_PRIORITY = {
    'salary': 0,
    'regular': 1,
    'overtime': 2,
    'double': 3,
    'pto': 4,
    'other': 10
}


class PayrollPayslip(models.Model):
    _name = 'payroll.payslip'
    _inherit = ['payslip.mixin', 'mail.thread', 'mail.activity.mixin']
    _description = 'Payslip for Employee'
    _order = 'pay_date, id'

    """
    Model structure:
    ├── address.mixin, geocode.mixin
    │   └── payslip.mixin
    │       ├── payroll.payslip
    """

    name = fields.Char('Name', compute='_compute_name', inverse='_inverse_name', store=True)
    employee_id = fields.Many2one('hr.employee', 'Employee', ondelete='restrict')
    pay_period_id = fields.Many2one('pay.period', 'Pay Period', ondelete='restrict')

    # Override
    company_id = fields.Many2one(related='pay_period_id.company_id', store=True)

    compensation_ids = fields.One2many('payslip.compensation', 'payslip_id', string='Compensations')
    deduction_ids = fields.One2many('payslip.deduction', 'payslip_id', string='Deductions')

    tax_ids = fields.One2many('payslip.tax', 'payslip_id', string='Tax Withholding')
    ee_tax_ids = fields.One2many('payslip.tax', 'payslip_id', string='Employee Tax Withholding', domain=[('is_er_tax', '=', False)])
    er_tax_ids = fields.One2many('payslip.tax', 'payslip_id', string='Company Tax Withholding', domain=[('is_er_tax', '=', True)])
    compout_ids = fields.One2many('payslip.compout', 'payslip_id', string='Compensation History')

    # Working Hours
    attendance_ids = fields.Many2many('hr.attendance', compute='_compute_attendance_ids_payslip', store=True, compute_sudo=True)
    outdated_working_hours = fields.Boolean('Working Hours Outdated', compute='_compute_outdated')
    worked_hours = fields.Float('Total Working Hours', digits=(16, 2))
    regular = fields.Float('Regular', digits=(16, 2))
    overtime = fields.Float('Overtime', digits=(16, 2))
    double_overtime = fields.Float('Double Overtime', digits=(16, 2))
    holiday = fields.Float('Total Paid Leaves Hours', digits=(16, 2))
    total_hours = fields.Float('Total Hours', compute='_compute_total_hours', store=True)

    # Paid Leaves
    payroll_vacation_ids = fields.One2many('payslip.vacation', 'payslip_id')
    outdated_leaves = fields.Boolean('Paid Leaves Outdated', compute='_compute_outdated')

    # Pay & Tax
    gross_pay = fields.Monetary('Gross Pay', compute='_compute_gross_pay', store=True)
    gross_pay_deduction = fields.Monetary('Gross Pay for Deduction', compute='_compute_gross_pay', store=True)
    net_pay = fields.Monetary('Net Pay')
    total_ee_tax = fields.Monetary('Total Employee Taxes')
    total_er_tax = fields.Monetary('Total Company Taxes')

    # Deduction
    total_ee_deduction = fields.Monetary('Total Employee Deduction')
    total_er_deduction = fields.Monetary('Total Company Contribution')

    # For import/export historical data
    wizard_compensation_ids = fields.Many2many('payroll.compensation', string='Historical Compensation',
                                               compute='_compute_wizard_compensation_ids', inverse='_inverse_wizard_compensation_ids',
                                               help='To add Compensation to historical Payslip in Wizard form')
    wizard_deduction_ids = fields.Many2many('payroll.deduction', string='Historical Deduction',
                                            compute='_compute_wizard_deduction_ids', inverse='_inverse_wizard_deduction_ids',
                                            help='To add Deduction to historical Payslip in Wizard form')

    # Related from Pay Period
    pay_date = fields.Date(related='pay_period_id.pay_date', store=True)
    start_date = fields.Date(related='pay_period_id.start_date', store=True)
    end_date = fields.Date(related='pay_period_id.end_date', store=True)
    pay_type = fields.Selection(related='pay_period_id.pay_type', store=True)
    is_history = fields.Boolean(related='pay_period_id.is_history', store=True)
    state = fields.Selection(related='pay_period_id.state', string='Payroll State', store=True)

    # Related from Overtime Rule
    workweek_start = fields.Selection(related='time_tracking_id.workweek_start', store=True)
    weekly_ovt = fields.Integer(related='time_tracking_id.weekly_ovt', store=True)
    weekly_ovt_apply = fields.Boolean(related='time_tracking_id.weekly_ovt_apply', store=True)
    daily_ovt = fields.Integer(related='time_tracking_id.daily_ovt', store=True)
    daily_ovt_apply = fields.Boolean(related='time_tracking_id.daily_ovt_apply', store=True)
    daily_double_ovt = fields.Integer(related='time_tracking_id.daily_double_ovt', store=True)
    daily_double_ovt_apply = fields.Boolean(related='time_tracking_id.daily_double_ovt_apply', store=True)
    consecutive_7_days = fields.Boolean(related='time_tracking_id.consecutive_7_days', store=True)

    # Override string and add inverse method
    salary_per_paycheck = fields.Monetary('Salary for this period', compute='_compute_payroll_salary',
                                          inverse='_inverse_salary_per_paycheck', store=True, tracking=True)

    # Technical fields to modify working hours/leaves/vacations manually
    manual_working_hours = fields.Boolean('Edit Working Hours manually', default=False)
    manual_leaves = fields.Boolean('Edit Leaves manually', default=False)

    is_negative_net_pay = fields.Boolean('Is Net Pay Negative?', default=False)

    # Technical fields for Account Direct Deposit
    payment_account_text = fields.Text('Payment Accounts (Json)')
    payment_account_html = fields.Html('Payment Accounts (Html)', compute='_compute_payment_account_html', store=True)

    period_pay_frequency_id = fields.Many2one(related='pay_period_id.pay_frequency_id', string='Frequency in Period',
                                              help='Technical field to know if Pay Frequency in this payslip is different from in the period.')

    ####################################################################################################################
    # CONSTRAINTS
    ####################################################################################################################
    def _check_period_date(self):
        """
        To be sure that start_date and end_date exist before getting working hours/leave days.
        :raise: UserError
        """
        self.ensure_one()
        if not (self.start_date and self.end_date):
            raise UserError(_('Please add Start Date and End Date for this Pay Period.'))

    def _check_time_tracking_rule(self):
        """
        To be sure that this payslip has been set time_tracking_id or not.
        :raise: UserError
        """
        self.ensure_one()
        if not self.time_tracking_id:
            raise UserError(_("""Please make sure this payslip has been set Overtime Rule.
            Check the employee's profile, then click 'Update Information' and try again."""))

    ####################################################################################################################
    # ONCHANGE, COMPUTE/INVERSE
    ####################################################################################################################
    @api.onchange('employee_id')
    def _onchange_employee_id(self):
        """
        Copy data from employee to payslip.
        Filter list of employees: Do not show employees which have been added or have different pay frequency with the first one.
        :return: domain
        """
        payroll_data = self.employee_id.copy_payroll_data()[0]
        self.update(payroll_data)

        period = self.pay_period_id

        emp_domain = [
            ('company_id', '=', self.company_id.id),
            ('id', 'not in', period.payslip_ids.mapped('employee_id').ids)
        ]
        if period.pay_frequency_id:
            emp_domain.append(('pay_frequency_id', '=', period.pay_frequency_id.id))

        return {'domain': {'employee_id': emp_domain}}

    @api.depends('start_date', 'end_date', 'pay_date', 'employee_id')
    def _compute_name(self):
        date_format = get_default_date_format(self)

        for record in self:
            if record.employee_id and record.pay_period_id:
                if record.pay_frequency_id and record.pay_type == 'frequency':
                    record.name = "Payslip of {} for period {} - {}".format(
                        record.employee_id.name,
                        record.start_date.strftime(date_format),
                        record.end_date.strftime(date_format))
                elif record.pay_date:
                    record.name = "Payslip of {} on {}".format(
                        record.employee_id.name,
                        record.pay_date.strftime(date_format))
                else:
                    raise ValidationError(_('Please fill in Pay Date of this Pay Period before adding new employees.'))

    def _inverse_name(self):
        return True

    def _inverse_salary_per_paycheck(self):
        pass

    @api.depends('salary_amount', 'salary_period', 'employee_type', 'num_of_paychecks', 'calculate_salary_by',
                 'pay_period_id.pay_type', 'pay_period_id.start_date', 'pay_period_id.end_date')
    def _compute_payroll_salary(self):
        """
        Override to compute salary for Off-cycle / Termination Payroll / Bonus based on period time.
        """
        super(PayrollPayslip, self)._compute_payroll_salary()

        for record in self.filtered(lambda r: not r.salary_overridden):
            if not (record.start_date and record.end_date) or record.employee_type == 'hourly':
                record.salary_per_paycheck = 0

            elif record.pay_type != 'frequency' or record.pay_type == 'frequency' and record.num_of_paychecks == 24 and record.calculate_salary_by == 'hour':
                working_hours_per_week = record._calculate_standard_working_hours_per_week()
                working_hours = record._calculate_standard_working_hours()
                record.salary_per_paycheck = record.salary_annual * working_hours / (working_hours_per_week * 52)

    @api.depends('salary_per_paycheck', 'compensation_ids.amount', 'state')
    def _compute_gross_pay(self):
        for record in self:
            # Only add salary amount of employee has type != hourly
            gross_pay = record.salary_per_paycheck if (record.state == 'draft' and record.employee_type != 'hourly') else 0
            record.gross_pay = gross_pay + sum(com.amount for com in record.compensation_ids)
            record.gross_pay_deduction = gross_pay + sum(com.amount for com in
                                                         record.compensation_ids.filtered(lambda x: x.incl_gp_deduction))

    @api.depends('start_date', 'end_date', 'workweek_start', 'employee_type',
                 'employee_id.attendance_ids', 'employee_id.attendance_ids.date', 'employee_id.attendance_ids.worked_hours')
    def _compute_attendance_ids_payslip(self):
        for record in self:
            if (
                    record.employee_type == 'salary'
                    or record.checkin_method != 'attendance'
                    or not (record.start_date and record.end_date)
                    or not record.employee_id.attendance_ids
            ):
                record.attendance_ids = False
                continue

            attendance_ids = record.employee_id.attendance_ids
            start_date = record.start_date
            end_date = record.end_date

            if record.workweek_start:
                workweek = int(record.workweek_start)
                start = start_date.weekday()
                start_date -= timedelta(days=start - workweek if start >= workweek else 7 + start - workweek)
            record.attendance_ids = attendance_ids.filtered(lambda r: start_date <= r.date <= end_date)

    @api.depends('worked_hours', 'holiday')
    def _compute_total_hours(self):
        for record in self:
            record.total_hours = record.worked_hours + record.holiday

    @api.depends('start_date', 'end_date', 'attendance_ids', 'payroll_vacation_ids', 'state', 'manual_working_hours', 'manual_leaves')
    def _compute_outdated(self):
        """
        Check if this payslip is outdated working hours / paid leaves, based on current values and new calculated values.
        To improve performance, ignore if this is not a Bonus Payroll, Historical Payroll or in draft state,
        the same if user wants to calculate manually.
        """
        for record in self:
            outdated_working_hours = outdated_leaves = False
            if record.state == 'draft' and record.pay_type != 'bonus' and not record.is_history:
                is_calculated = bool(record.employee_id and record.start_date and record.end_date)

                # Working Hours
                if not record.manual_working_hours:
                    working_hours = record.get_working_hours() if is_calculated else {
                        'worked_hours': False,
                        'regular': False,
                        'overtime': False,
                        'double_overtime': False
                    }
                    outdated_working_hours = any(working_hours[field] != record[field] for field in working_hours)

                # Time Off
                if not record.manual_leaves:
                    holiday_hours = record.get_holiday_hours()[1] if is_calculated else False
                    outdated_leaves = holiday_hours != record.holiday

            record.outdated_working_hours = outdated_working_hours
            record.outdated_leaves = outdated_leaves

    @api.depends('payment_account_text', 'split_paychecks_type')
    def _compute_payment_account_html(self):
        account_env = self.env['account.payment.direct']

        for record in self:
            payment_account_text = json.loads(record.payment_account_text or '[]')
            if not payment_account_text:
                record.payment_account_html = False
            else:
                rows = ''
                for line in payment_account_text:
                    amount = record._format_currency_amount(line['amount_fixed']) if line['split_paychecks_type'] == 'amount' else line['amount_percentage']
                    rows += """
                        <tr>
                            <td class="pl-5">{account_name}</td>
                            <td>{routing_number}</td>
                            <td>{account_number}</td>
                            <td>{account_type}</td>
                            <td class="text-right pr-5">{amount}</td>
                        </tr>
                    """.format(
                        account_name=line['account_name'],
                        routing_number=line['routing_number'],
                        account_number=line['account_number'],
                        account_type=dict(account_env._fields['account_type'].selection).get(line['account_type']),
                        amount=amount
                    )

                record.payment_account_html = """
                    <table class="o_list_table table table-sm table-hover table-striped" style="table-layout:fixed">
                        <thead>
                            <tr>
                                <th class="pl-5">Account Name</th>
                                <th>Routing Number</th>
                                <th>Account Number</th>
                                <th>Account Type</th>
                                <th class="pr-5">{split_type}</th>
                            </tr>
                        </thead>
                        <tbody>
                            {rows}
                        </tbody>
                    </table>
                """.format(
                    split_type='Fixed Amount' if record.split_paychecks_type == 'amount' else 'Percentage',
                    rows=rows
                )

    # Historical Data --------------------------------------------------------------------------------------------------
    def _compute_wizard_compensation_ids(self):
        for record in self:
            record.wizard_compensation_ids = record.compensation_ids.mapped('compensation_id') if record.is_history else False

    def _inverse_wizard_compensation_ids(self):
        for record in self.filtered('is_history'):
            new_compensation_ids = record.wizard_compensation_ids - record.compensation_ids.mapped('compensation_id')
            if new_compensation_ids:
                record.compensation_ids = [(0, 0, {'compensation_id': comp_id.id, 'is_regular': True}) for comp_id in new_compensation_ids]

    def _compute_wizard_deduction_ids(self):
        for record in self:
            record.wizard_deduction_ids = record.deduction_ids.mapped('deduction_id') if record.is_history else False

    def _inverse_wizard_deduction_ids(self):
        for record in self.filtered('is_history'):
            new_deduction_ids = record.wizard_deduction_ids - record.deduction_ids.mapped('deduction_id')
            if new_deduction_ids:
                record.deduction_ids = [(0, 0, {'deduction_id': ded_id.id, 'is_regular': True}) for ded_id in new_deduction_ids]

    ####################################################################################################################
    # ACTION
    ####################################################################################################################
    def button_work_log_attendance(self):
        self.ensure_one()
        view_id = self.env.ref('l10n_us_hr_payroll.view_payroll_attendance_tree')
        attendance_ids = self.attendance_ids and self.attendance_ids.ids or False

        return {
            'name': 'Attendances - {}'.format(self.employee_id.name),
            'view_mode': 'tree',
            'res_model': 'hr.attendance',
            'view_id': view_id.id,
            'domain': [('id', 'in', attendance_ids), ('date', '>=', self.start_date)],
            'type': 'ir.actions.act_window',
            'target': 'new',
            'context': {
                'disable_selector': True
            }
        }

    def button_see_employee_leave(self):
        self.ensure_one()
        view_id = self.env.ref('l10n_us_hr_payroll.view_payroll_leave_tree')
        domain = [
            ('employee_id', '=', self.employee_id.id),
            ('state', '=', 'validate'),
            '|',
                '&', ('request_date_from', '<=', self.start_date), ('request_date_to', '>=', self.start_date),
                '&', ('request_date_from', '>', self.start_date), ('request_date_from', '<=', self.end_date)
        ]

        return {
            'name': 'Leaves - {}'.format(self.employee_id.name),
            'view_mode': 'tree',
            'res_model': 'hr.leave',
            'view_id': view_id.id,
            'domain': domain,
            'type': 'ir.actions.act_window',
            'target': 'new',
            'context': {
                'disable_selector': True
            }
        }

    def button_get_working_hours(self):
        self.ensure_one()
        if self.manual_working_hours:
            return

        hours = self.get_working_hours()
        self.write(hours)

    def action_get_working_hours(self):
        for record in self:
            record.button_get_working_hours()

    def button_get_holiday_hours(self):
        """
        Get Paid Leaves for this period.
        """
        self.ensure_one()
        if self.manual_leaves:
            return

        self._check_period_date()
        if self.payroll_vacation_ids:
            # Remove all data if user hits this button
            self.payroll_vacation_ids.unlink()
        vacation_datas, holiday_hours = self.get_holiday_hours()

        if vacation_datas:
            self.env['payslip.vacation'].create(vacation_datas)
        self.holiday = holiday_hours

        # For Salary/No Overtime employees, working_hours + holiday = standard working hours.
        if self.employee_type == 'salary':
            standard = self._calculate_standard_working_hours()
            self.worked_hours = self.regular = standard - self.holiday

    def action_get_holiday_hours(self):
        for record in self:
            record.button_get_holiday_hours()

    def button_print_check(self):
        self.ensure_one()
        return self.print_checks()

    def button_update_payroll_info(self):
        self.ensure_one()
        payroll_data = self.employee_id.copy_payroll_data()[0]
        self.write(payroll_data)

    def action_update_payroll_info(self):
        for record in self:
            record.button_update_payroll_info()

    def button_update_salary_per_paycheck(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Update Salary for this period',
            'view_mode': 'form',
            'view_id': self.env.ref('l10n_us_hr_payroll.view_payroll_payslip_update_salary').id,
            'res_model': self._name,
            'res_id': self.id,
            'target': 'new',
        }

    def save_salary_per_paycheck(self):
        # Just to save the payslip popup
        return

    def action_confirm(self):
        self.write({'is_negative_net_pay': False})

        self._update_compensation_list()
        # Calculate accumulated amt from previous period first, then deduction
        self._calculate_accumulated_amount()
        self._calculate_deduction_amount(before=True)

        # Send to Vertex to get tax
        Vertex().get_payroll_result_list(self)

        self._calculate_net_pay()
        # Calculate deduction first, then accumulated amt
        self._calculate_deduction_amount()
        self._calculate_accumulated_amount()
        self._calculate_total_deduction()

    def button_draft(self):
        """
        This function is used to remove things when set back to draft:
        - Special compensation lines
        - Taxes
        - CompOut
        """
        self.ensure_one()
        self._calculate_accumulated_amount()
        vals = {
            'tax_ids': [(2, x.id) for x in self.tax_ids],
            'compout_ids': [(2, x.id) for x in self.compout_ids],
            'net_pay': 0,
            'total_ee_tax': 0,
            'total_er_tax': 0,
            'total_ee_deduction': 0,
            'total_er_deduction': 0
        }
        compensations = self.compensation_ids.filtered(lambda x: x.is_salary)
        if compensations:
            vals.update({'compensation_ids': [(2, x.id) for x in compensations]})
        self.sudo().write(vals)
        self.deduction_ids.write({
            'amount': 0,
            'owed_payslip_remaining_amount': 0
        })

    def action_draft(self):
        for record in self:
            record.button_draft()

    ####################################################################################################################
    # CRUD
    ####################################################################################################################
    @api.model
    def create(self, vals):
        res = super(PayrollPayslip, self).create(vals)
        res.action_update_payroll_info()
        res.filtered(lambda r: r.start_date and r.end_date).get_all_hours()
        return res

    ####################################################################################################################
    # HELPER METHODS
    ####################################################################################################################
    def get_working_hours(self):
        """
        Method to get all working hours.
        Format them using float_round.
        """
        self.ensure_one()
        self._check_period_date()
        total = regular = overtime = double = 0

        if self.employee_type == 'salary':
            total = self._calculate_standard_working_hours()
            total -= self.holiday if self.holiday else 0
            regular, overtime, double = total, False, False
        elif self.checkin_method == 'attendance':
            total, regular, overtime, double = self._get_working_hours_template('attendance_ids', 'worked_hours')

        return {
            'worked_hours': float_round(total, precision_digits=2),
            'regular': float_round(regular, precision_digits=2),
            'overtime': float_round(overtime, precision_digits=2),
            'double_overtime': float_round(double, precision_digits=2)
        }

    def _get_working_hours_template(self, field_get, calculate_by):
        """
        Get all working hours.
        By passing different params we could use this method to apply for other check-in app, such as Timesheets.

        :param field_get: 'attendance_ids' (by default)
        :param calculate_by: 'worked_hours' (by default)
        :return: (total, regular, overtime, double)
        """
        self._check_time_tracking_rule()
        return get_all_working_hours(
            field_ids=self[field_get],
            calculate_by=calculate_by,
            workweek=int(self.workweek_start),
            start_date=self.start_date,
            end_date=self.end_date,
            weekly_ovt=self.weekly_ovt_apply and self.weekly_ovt or 0,
            daily_ovt=self.daily_ovt_apply and self.daily_ovt or 0,
            double_ovt=self.daily_double_ovt_apply and self.daily_double_ovt or 0,
            consecutive_7_days=self.consecutive_7_days
        )

    def get_holiday_hours(self):
        self.ensure_one()
        leave_env = self.env['hr.leave']

        # Use timezone from resource.calendar of payslip.
        resource_calendar_id = self.resource_calendar_id or self.env.company.resource_calendar_id
        tz = resource_calendar_id.tz

        # Convert start_date and end_date to datetime
        start_date = datetime.combine(self.start_date, time.min)
        end_date = datetime.combine(self.end_date, time.max)

        # Get remaining leaves and current leaves (maybe include leaves out of this period)
        # Ex: Period from 07/10/2019 to 07/17/2019, leave request from 07/09/2019 to 07/11/2019
        remaining_leaves = self._get_remaining_leaves(self.employee_id.id, start_date, end_date, tz)
        cur_leaves = self._get_leaves(self.employee_id.id, start_date, end_date, tz)

        vals_list = []
        compensation_holiday_id = self.env.ref('l10n_us_hr_payroll.payroll_compensation_holiday').id

        for remaining_leave in remaining_leaves:
            leave_type = remaining_leave['leave_type']
            compensation_id = remaining_leave['compensation_id']

            # in_days, in_hours: actual days/hours off used in this pay period.
            # out_days, out_hours: days/hours off which are out of this period.
            in_days = in_hours = out_days = out_hours = 0

            current_leave = list(filter(lambda x: x['leave_type'] == leave_type, cur_leaves))
            leave_ids = current_leave and current_leave[0]['leaves']

            for leave_id in leave_env.browse(leave_ids):
                leave_date_from, leave_date_to = leave_id.date_from, leave_id.date_to

                # Compute part of leave request belongs to this period.
                date_from = max(leave_date_from, start_date)
                date_to = min(leave_date_to, end_date)

                # Compute actual days/hours off used in this period.
                # compute_leaves=True (default) will check leave requests in get_work_days_data(), then return 0.
                current_off = resource_calendar_id.get_work_days_data(date_from, date_to, compute_leaves=False)

                in_days += current_off['days']
                in_hours += current_off['hours']

                # Part of days off in the future has not been used. Do not include it in balance.
                if leave_date_to > end_date:
                    future_off = resource_calendar_id.get_work_days_data(end_date, leave_date_to)
                    out_days += future_off['days']
                    out_hours += future_off['hours']

            # Calculate balance of paid leaves
            # Public Holidays or Leave Types having Mode = No Allocation will have balance = 0
            if compensation_id == compensation_holiday_id or remaining_leave['mode'] == 'no':
                remaining_days = remaining_hours = 0.0
            else:
                remaining_days = remaining_leave['days'] + out_days
                remaining_hours = remaining_leave['hours'] + out_hours

            vals_list.append({
                'leave_type_id': leave_type,
                'payslip_id': self.id,
                'payroll_compensation_id': compensation_id,
                'remaining_leave_days': remaining_days,
                'remaining_leave_hours': remaining_hours,
                'number_of_days': in_days,
                'number_of_hours': in_hours,
            })

        holiday_hours = float_round(sum(val['number_of_hours'] for val in vals_list), precision_digits=2)
        return vals_list, holiday_hours

    @api.model
    def _get_leaves(self, employee_id, start_date, end_date, tz=False):
        """
        Compute all paid leaves for current employee in this period.
        :param employee_id: id of current employee.
        :param start_date: (timestamp) start date of this period.
        :param end_date: (timestamp) end date of this period.
        :param tz: timezone of resource.calendar
        :returns: dict (leave_type, compensation_id, leaves: list)
        """
        sql_query = """
            SELECT
                lt.id AS leave_type,
                lt.payroll_compensation_id AS compensation_id,
                ARRAY_AGG(l.id) AS leaves
            FROM hr_leave l
                JOIN hr_leave_type lt ON lt.id=l.holiday_status_id
                JOIN hr_employee ee ON ee.id=l.employee_id
            WHERE
                NOT lt.unpaid AND
                (
                    ee.employee_type = 'salary' AND lt.emp_type_salary IS TRUE
                    OR ee.employee_type = 'salary_ovt' AND lt.emp_type_salary_ovt IS TRUE
                    OR ee.employee_type = 'hourly' AND lt.emp_type_hourly IS TRUE
                ) AND
                lt.payroll_compensation_id IS NOT NULL AND
                l.state = 'validate' AND
                l.employee_id = {emp_id} AND
                (
                    l.date_from AT TIME ZONE '{tz}' BETWEEN '{start}' AND '{end}' OR
                    l.date_from AT TIME ZONE '{tz}' < '{start}' AND l.date_to AT TIME ZONE '{tz}' >= '{start}'
                )
            GROUP BY leave_type, lt.sequence
            ORDER BY lt.sequence
            """.format(emp_id=employee_id, start=start_date, end=end_date, tz=tz)

        self._cr.execute(sql_query)
        return self._cr.dictfetchall()

    @api.model
    def _get_remaining_leaves(self, employee_id, start_date, end_date, tz=False):
        """
        Helper to compute the remaining leaves for the current employees
        :param: employee_id
        :returns dict (leave_type, compensation_id, mode, days, hours).
        """
        sql_query = """
            SELECT
                lt.id AS leave_type,
                lt.payroll_compensation_id AS compensation_id,
                lt.allocation_type AS mode,
                sum(h.number_of_days) AS days,
                sum(h.number_of_hours) AS hours
            FROM
                (
                    SELECT
                        id,
                        holiday_status_id, state, employee_id,
                        number_of_days,
                        number_of_hours_display as number_of_hours
                    FROM hr_leave_allocation
                    UNION
                    SELECT
                        id,
                        holiday_status_id, state, employee_id,
                        (number_of_days * -1) as number_of_days,
                        (number_of_hours_display * -1) as number_of_hours
                    FROM hr_leave
                    WHERE date_from AT TIME ZONE '{tz}' < '{end}'
                ) h
                JOIN hr_leave_type lt ON lt.id=h.holiday_status_id
                JOIN hr_employee ee ON ee.id=h.employee_id
            WHERE
                NOT lt.unpaid AND
                (
                    ee.employee_type = 'salary' AND lt.emp_type_salary IS TRUE
                    OR ee.employee_type = 'salary_ovt' AND lt.emp_type_salary_ovt IS TRUE
                    OR ee.employee_type = 'hourly' AND lt.emp_type_hourly IS TRUE
                ) AND
                lt.payroll_compensation_id IS NOT NULL AND
                (
                    lt.validity_start IS NULL AND lt.validity_stop IS NULL
                    OR lt.validity_start IS NULL AND lt.validity_stop AT TIME ZONE '{tz}' >= '{start}'
                    OR lt.validity_stop IS NULL AND lt.validity_start AT TIME ZONE '{tz}' <= '{end}'
                    OR lt.validity_start AT TIME ZONE '{tz}' <= '{start}' AND lt.validity_stop AT TIME ZONE '{tz}' >= '{start}' 
                    OR lt.validity_start AT TIME ZONE '{tz}' >= '{start}' AND lt.validity_start AT TIME ZONE '{tz}' <= '{end}'
                ) AND
                h.state = 'validate' AND
                h.employee_id = {emp_id}
            GROUP BY leave_type, lt.sequence
            ORDER BY lt.sequence
        """.format(emp_id=employee_id, tz=tz, start=start_date, end=end_date)

        self._cr.execute(sql_query)
        return self._cr.dictfetchall()

    def do_print_check(self):
        """
        This is extendable function for printing check
        """
        raise UserError(_("You have to choose a check layout. For this, go in Apps, search for 'US Checks Layout for payslip' and install one."))

    def print_checks(self):
        """
        This is extendable function for printing check
        """
        return self.do_print_check()

    def _calculate_accumulated_amount(self, tax=False, compout=False):
        for record in self:
            if record.compensation_ids:
                record.compensation_ids.calculate_accumulated_amount()
            if record.deduction_ids:
                record.deduction_ids.calculate_accumulated_amount()
                record.deduction_ids.with_context(is_employer=True).calculate_accumulated_amount(amount='er_dollar_amt')
            if record.tax_ids and tax:
                record.tax_ids.calculate_accumulated_amount(amount='tax_amt')
                record.tax_ids.with_context(adj_gross=True).calculate_accumulated_amount(amount='actual_adjusted_gross')
            if record.compout_ids and compout:
                record.compout_ids.calculate_accumulated_amount(amount='amt')
        return True

    def _calculate_standard_working_hours(self):
        """
        Get working hours for Salary (No Overtime) Employee.
        """
        self.ensure_one()
        start, end = self.start_date, self.end_date
        if not (start and end):
            return 0
        hours_per_week = self._calculate_standard_working_hours_per_week()

        # For Scheduled Payroll, if `Salary calculated by` = "Fixed per Paycheck",
        # this should be based on working hours per week and frequency of period.
        if self.calculate_salary_by == 'paycheck' and self.pay_type == 'frequency':
            frequency = int(self.pay_frequency_id.frequency or 0)
            return hours_per_week * 52 / frequency

        days = (end - start).days + 1
        div, mod = divmod(days, 7)
        working_hours = div * hours_per_week

        attendance_ids = self.resource_calendar_id.attendance_ids
        date = self.end_date
        while mod:
            att_ids = attendance_ids.filtered(lambda r: r.dayofweek == str(date.weekday()))
            for att in att_ids:
                working_hours += att.hour_to - att.hour_from
            date -= timedelta(days=1)
            mod -= 1

        return working_hours

    def _reset_working_hours(self):
        self.write({
            'worked_hours': False,
            'regular': False,
            'overtime': False,
            'double_overtime': False,
        })

    def _reset_holiday_hours(self):
        self.write({'holiday': False})
        self.mapped('payroll_vacation_ids').unlink()

    def get_all_hours(self):
        self.action_get_holiday_hours()
        self.action_get_working_hours()

    def reset_all_hours(self):
        self._reset_working_hours()
        self._reset_holiday_hours()

    @api.model
    def create_compensation(self, com_id, label, employee_id, amount, rate, hours, sequence, is_salary=True, is_regular=True):
        """
        Get the values dict to create new payslip compensation
        """
        return {
            'compensation_id': com_id,
            'label': label,
            'employee_id': employee_id,
            'amount': float_round(amount, precision_digits=2),
            'rate': float_round(rate, precision_digits=2),
            'hours': hours,
            'is_salary': is_salary,
            'is_regular': is_regular,
            'sequence': sequence
        }

    def _update_compensation_list(self):
        """
        This function is used to update compensation list before running payroll.
        Add Salary line (for salary/hourly employee)
        Add Vacation/Sick Pay
        """
        overtime_rate = self.env.company.overtime_rate
        double_rate = self.env.company.double_overtime_rate

        for record in self:
            compensations = []
            salary_amount = record.salary_per_paycheck
            hourly_rate = record.pay_rate
            employee_type = record.employee_type

            # Don't add Compensation if it's a history data or salary_amount = 0
            if (
                    record.is_history or
                    employee_type != 'hourly' and not salary_amount or
                    employee_type == 'hourly' and not hourly_rate
            ):
                continue

            # PTO (for All)
            total_pto = 0
            if record.payroll_vacation_ids:
                for leave in record.payroll_vacation_ids:
                    if leave.number_of_hours:
                        com_id = leave.payroll_compensation_id.id
                        label = leave.payroll_compensation_id.name
                        amount = hourly_rate * leave.number_of_hours
                        comp = self.create_compensation(com_id, label, record.employee_id.id, amount, hourly_rate,
                                                        leave.number_of_hours, SEQUENCE_PRIORITY['pto'])
                        compensations.append(comp)
                        total_pto += amount

            # Regular Pay (for All)
            com_id = record.env.ref(SALARY_TYPE['regular']).id
            regular_hours = record.regular
            if employee_type == 'hourly':
                label = 'Regular Pay'
                amount = hourly_rate * regular_hours
                comp = self.create_compensation(com_id, label, record.employee_id.id, amount, hourly_rate, regular_hours, SEQUENCE_PRIORITY['regular'])
                compensations.append(comp)
            else:
                label = 'Salary'
                # or amount = hourly_rate * regular_hours, but won't be accurate.
                amount = salary_amount - total_pto
                if employee_type == 'salary_ovt':
                    regular_hours = record._calculate_standard_working_hours() - record.holiday
                # Error will be raised if user add paid leaves manually with pto amount greater than salary amount
                if amount > 0:
                    comp = self.create_compensation(com_id, label, record.employee_id.id, amount, hourly_rate, regular_hours, SEQUENCE_PRIORITY['salary'])
                    compensations.append(comp)

            # Overtime and Double Overtime Pay (for `Salary/Eligible for Overtime` and `Hourly` Employees)
            if employee_type != 'salary':
                if record.overtime:
                    com_id = record.env.ref(SALARY_TYPE['overtime']).id
                    label = 'Overtime Pay'
                    rate = overtime_rate * hourly_rate
                    amount = rate * record.overtime
                    comp = self.create_compensation(com_id, label, record.employee_id.id, amount, rate, record.overtime, SEQUENCE_PRIORITY['overtime'])
                    compensations.append(comp)
                if record.double_overtime:
                    com_id = record.env.ref(SALARY_TYPE['double']).id
                    label = 'Double Overtime Pay'
                    rate = double_rate * hourly_rate
                    amount = rate * record.double_overtime
                    comp = self.create_compensation(com_id, label, record.employee_id.id, amount, rate,
                                                    record.double_overtime, SEQUENCE_PRIORITY['double'])
                    compensations.append(comp)

            record.write({'compensation_ids': [(0, 0, x) for x in compensations]})

    def _calculate_deduction_amount(self, before=False):
        """
        This function is used to calculate deduction dollar amount.
        We need to call it twice:
        - Before Vertex: for pretax + fix/% Gross post-tax deduction
        - After Vertex: for the rest (% Net, % Disposable). But we still need to calculate Max % of Net anyway.
        :param before: before Vertex
        """
        for record in self:
            deductions = record.deduction_ids
            if before:
                deductions = record.deduction_ids.filtered(lambda x: x.vertex_id or x.ee_post_amount_type in ['fixed', 'percentage'])
            else:
                deductions._get_disposable_income()
            deductions._calculate_owed_payslip_remaining_amount()
            deductions._get_deduction_dollar_amt()

    def _calculate_net_pay(self):
        """
        Run after get tax result from Vertex.
        :return:
        Total Employee Tax
        Total Employer Tax
        Net Pay: Gross - EE Tax - Pre-tax Deduction
        """
        for record in self:
            total_ee_tax = sum(tax.tax_amt for tax in record.tax_ids.filtered(lambda x: not x.is_er_tax))
            total_er_tax = sum(tax.tax_amt for tax in record.tax_ids.filtered(lambda x: x.is_er_tax))

            total_pretax_deduction = sum(ded.amount for ded in record.deduction_ids.filtered(lambda x: x.vertex_id))
            net_pay = record.gross_pay - total_ee_tax - total_pretax_deduction

            record.write({'total_ee_tax': total_ee_tax,
                          'total_er_tax': total_er_tax,
                          'net_pay': net_pay})

    def _calculate_net_pay_history_done(self):
        """
        Only run when click Done on Historical Payroll
        """
        for record in self:
            total_ee_tax = sum(tax.tax_amt for tax in record.tax_ids.filtered(lambda x: not x.is_er_tax))
            total_er_tax = sum(tax.tax_amt for tax in record.tax_ids.filtered(lambda x: x.is_er_tax))

            net_pay = record.gross_pay - total_ee_tax - record.total_ee_deduction
            record.write({'total_ee_tax': total_ee_tax,
                          'total_er_tax': total_er_tax,
                          'net_pay': net_pay})

    def _calculate_total_deduction(self):
        """
        Calculate total EE & ER Deduction.
        Have to calculate Net Pay again to exclude Post-Tax Deduction
        """
        for record in self:
            total_ee_deduction = sum(com.amount for com in record.deduction_ids)
            total_er_deduction = sum(com.er_dollar_amt for com in record.deduction_ids)
            net_pay = record.gross_pay - total_ee_deduction - record.total_ee_tax

            record.write({'total_ee_deduction': total_ee_deduction,
                          'total_er_deduction': total_er_deduction,
                          'net_pay': net_pay})

    def _generate_ach_ppd_entries(self):
        """
        Apply for payslips having payment_method = 'deposit', split Net Pay into multiple parts
        based on Fixed Amount/Percentage of Payment Accounts, then generate PPD entries for them.
        """
        def generate_entry_detail(payment_account, amount, type=22):
            """
            Create entry object to use in ach.builder
            :param payment_account: dict of values got from account.payment.direct.read()
            :param amount: net_pay for this payment_account
            :param type: ACH Transaction Codes
            :return: entry object
            """
            # TODO: type
            # amount = 0 => 29 if payment_type = 'inbound' else 24
            # else 27 if payment_type = 'inbound' else 22
            return {
                'type': type,
                'routing_number': payment_account['routing_number'],
                'account_number': payment_account['account_number'],
                'amount': amount,
                'name': payment_account['account_name']
            }

        period_entries = list()
        payslip_ids = self.filtered(lambda r: r.payment_method == 'deposit')

        for record in payslip_ids:
            payslip_entries = list()
            net_pay = record.net_pay
            payment_accounts = json.loads(record.payment_account_text or '[]')
            if not payment_accounts:
                continue

            if record.split_paychecks_type == 'percentage':
                for account in payment_accounts[:-1]:
                    amount = float_round(net_pay * account['amount_percentage'] / 100, precision_digits=2)
                    payslip_entries.append(generate_entry_detail(account, amount))
                last_amount = net_pay - sum(account.get('amount') for account in payslip_entries)
            else:
                for account in payment_accounts[:-1]:
                    # Ignore other accounts if current net pay <= 0
                    if float_compare(net_pay, 0, precision_digits=2) != 1:
                        break
                    amount = min(net_pay, account['amount_fixed'])
                    payslip_entries.append(generate_entry_detail(account, amount))
                    net_pay -= amount
                last_amount = net_pay

            # Add last account if remaining net pay > 0
            if float_compare(last_amount, 0, precision_digits=2) == 1:
                payslip_entries.append(generate_entry_detail(payment_accounts[-1], last_amount))

            period_entries += payslip_entries

        return period_entries
