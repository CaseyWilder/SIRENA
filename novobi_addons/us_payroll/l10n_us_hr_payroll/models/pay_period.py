import logging

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools.float_utils import float_round, float_is_zero

from ..utils.utils import get_default_date_format, calculate_current_period

_logger = logging.getLogger(__name__)

try:
    from ach.builder import AchFile
except ImportError as e:
    AchFile = None
    _logger.error(e)


PERIOD_ACTION_VIEW = {
    'frequency': 'l10n_us_hr_payroll.action_pay_period_form_frequency',
    'off': 'l10n_us_hr_payroll.action_pay_period_form_off_cycle',
    'bonus': 'l10n_us_hr_payroll.action_pay_period_form_bonus',
    'termination': 'l10n_us_hr_payroll.action_pay_period_form_termination'
}

MENU_VIEW = 'l10n_us_hr_payroll.menu_us_payroll_root'


class PayPeriod(models.Model):
    _name = 'pay.period'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Pay Period'
    _order = 'pay_date, id'

    name = fields.Char('Name', compute='_compute_name', inverse='_inverse_name', store=True)
    is_history = fields.Boolean('Is this a historical payroll data?')
    pay_frequency_id = fields.Many2one('pay.frequency', compute='_compute_pay_frequency_id',
                                       inverse='_inverse_pay_frequency_id', store=True, ondelete='restrict')
    payslip_ids = fields.One2many('payroll.payslip', 'pay_period_id', string='Payslips')
    start_date = fields.Date('Start Date')
    end_date = fields.Date('End Date')
    pay_date = fields.Date('Pay Date')
    state = fields.Selection([('draft', 'Draft'), ('confirmed', 'Confirmed'), ('done', 'Done')], default='draft')
    move_id = fields.Many2one('account.move', string='Payroll Journal Entry')
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)

    # ===== Helper fields ====
    quarter = fields.Integer('Quarter', compute='_compute_quarter', store=True)
    number_periods = fields.Integer('Number of Pay Periods in Year', help='This field is for sending to Vertex')
    current_period = fields.Integer('Current Period of Frequency', help='This field is for sending to Vertex')

    outdated_working_hours = fields.Boolean('Working Hours Outdated', compute='_compute_outdated')
    outdated_leaves = fields.Boolean('Paid Leaves Outdated', compute='_compute_outdated')
    missing_employees = fields.Boolean('Missing Employees?', compute='_compute_missing_employees')
    total_employees_count = fields.Integer('Total Employees', compute='_compute_total_employees_count')

    # Frequency, Off-cycle, Bonus or Termination
    pay_type = fields.Selection([
        ('frequency', 'Scheduled'),
        ('off', 'Off-cycle'),
        ('bonus', 'Bonus'),
        ('termination', 'Termination')
    ], string='Pay Type')

    # ===== Total amount =====
    currency_id = fields.Many2one('res.currency', string='Currency', default=lambda self: self.env.company.currency_id)
    total_gross_pay = fields.Monetary('Total Gross Pay', compute='_compute_total_amount', store=True)
    total_net_pay = fields.Monetary('Total Net Pay', compute='_compute_total_amount', store=True)

    ####################################################################################################################
    # CONSTRAINTS
    ####################################################################################################################
    @api.constrains('payslip_ids')
    def _check_payslip_ids(self):
        """
        Check valid condition of payslip_ids.
        :raise: ValidationError: if employees have been added to this pay period multiple times
        :raise: ValidationError: if all payslips do not have same frequency_id
        """
        self._check_unique_employee()
        self._check_unique_frequency()

    @api.constrains('start_date', 'end_date', 'pay_date')
    def _check_date_of_period(self):
        for record in self:
            errors = record._get_error_check_date_of_period()
            if errors:
                raise ValidationError(errors)

    def _check_unique_employee(self):
        for record in self:
            lst = []
            invalid_ids = set()
            for payslip in record.payslip_ids:
                employee_id = payslip.employee_id
                invalid_ids.add(employee_id) if employee_id.id in lst else lst.append(employee_id.id)
            if invalid_ids:
                names = '- ' + '\n- '.join(emp.name for emp in invalid_ids)
                raise ValidationError(_("""These employees have been added to this Pay Period multiple times:
                {}\nPlease remove all the duplicates and try again.""").format(names))

    def _check_unique_frequency(self):
        for record in self:
            if len(record.payslip_ids.filtered(lambda r: r.pay_frequency_id != record.pay_frequency_id)) > 0:
                raise ValidationError(_('Please make sure all employees in this period have the same pay frequency, '
                                        'then click "Update Information" and try again.'))

    def _get_error_check_date_of_period(self):
        """If pay_type != Bonus, End Date must be greater than Start Date."""
        error = ''
        if self.pay_type != 'bonus':
            start_date, end_date = self.start_date, self.end_date
            pay_date = self.pay_date
            if start_date and end_date and start_date >= end_date:
                error += _('End Date must be greater than Start Date.\n')
            if pay_date and end_date and pay_date < end_date:
                error += _('Pay Date cannot be less than End Date.\n')
        return error

    ####################################################################################################################
    # ONCHANGE, COMPUTE/INVERSE
    ####################################################################################################################
    @api.depends('payslip_ids', 'payslip_ids.pay_frequency_id', 'pay_type')
    def _compute_pay_frequency_id(self):
        """
        Pay frequency of a pay.period (except Scheduled Payroll) will be same to pay frequency of the first payslip
        to make sure all payslips in this payroll having same pay frequency.
        """
        for record in self:
            if record.pay_type != 'frequency':
                record.pay_frequency_id = record.payslip_ids and record.payslip_ids[0].pay_frequency_id or False

    def _inverse_pay_frequency_id(self):
        pass

    @api.depends('pay_frequency_id', 'pay_type')
    def _compute_name(self):
        date_format = get_default_date_format(self)
        for record in self:
            if record.pay_type == 'frequency' and record.pay_frequency_id and record.start_date and record.end_date and not record.name:
                record.name = "{} for period {} - {}".format(
                    record.pay_frequency_id.name,
                    record.start_date.strftime(date_format),
                    record.end_date.strftime(date_format)
                )

    def _inverse_name(self):
        return True

    @api.depends('payslip_ids')
    def _compute_total_employees_count(self):
        # Get number of employees (payslips) in this period
        for record in self:
            record.total_employees_count = len(record.payslip_ids)

    @api.depends('payslip_ids.outdated_working_hours', 'payslip_ids.outdated_leaves', 'start_date', 'end_date', 'state')
    def _compute_outdated(self):
        for record in self:
            outdated_working_hours = outdated_leaves = False
            if record.state == 'draft' and record.pay_type != 'bonus' and not record.is_history:
                is_period = bool(record.start_date and record.end_date)
                outdated_working_hours = is_period and True in record.payslip_ids.mapped('outdated_working_hours')
                outdated_leaves = is_period and True in record.payslip_ids.mapped('outdated_leaves')

            record.outdated_working_hours = outdated_working_hours
            record.outdated_leaves = outdated_leaves

    @api.depends('payslip_ids', 'payslip_ids.gross_pay', 'payslip_ids.net_pay')
    def _compute_total_amount(self):
        for period in self:
            if period.payslip_ids:
                period.total_gross_pay = sum(period.payslip_ids.mapped('gross_pay'))
                period.total_net_pay = sum(period.payslip_ids.mapped('net_pay'))

    def _compute_missing_employees(self):
        for record in self:
            employee_ids = self.env['hr.employee']
            if record.pay_type == 'frequency' and record.state == 'draft':
                employee_ids = employee_ids.search(record._get_missing_employees_domain())
            record.missing_employees = True if employee_ids else False

    @api.depends('pay_date')
    def _compute_quarter(self):
        for record in self:
            record.quarter = record.pay_date and (record.pay_date.month - 1) // 3 + 1 or False

    ####################################################################################################################
    # ACTION
    ####################################################################################################################
    def button_update_information(self):
        self.payslip_ids.action_update_payroll_info()

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success!'),
                'type': 'success',
                'message': _('All payslips in this period have been updated information.'),
                'next': {'type': 'ir.actions.act_window_close'},
            }
        }

    def button_update_working_hours(self):
        self._check_period_date()
        self._check_time_tracking_rule()
        self._check_standard_working_hours()
        self.payslip_ids.action_get_working_hours()

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success!'),
                'type': 'success',
                'message': _('All payslips in this period have been updated working hours.'),
                'next': {'type': 'ir.actions.act_window_close'},
            }
        }

    def button_update_leaves(self):
        self._check_period_date()
        self._check_standard_working_hours()
        self.payslip_ids.action_get_holiday_hours()

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success!'),
                'type': 'success',
                'message': _('All payslips in this period have been updated paid leaves.'),
                'next': {'type': 'ir.actions.act_window_close'},
            }
        }

    def button_add_missing_employees(self):
        self.ensure_one()
        action = self.env.ref('l10n_us_hr_payroll.action_add_missing_employees_wizard').read()[0]
        action['context'] = {
            'default_period_id': self.id
        }
        return action

    def _confirm_immediately(self):
        """
        Run Payroll immediately (after checking all conditions). Do not call this method individually.
        Current user will auto follow this period.
        If all payslips have positive net pay:
            - Send an email to notify to all followers that this period has been processed
            - Mark this period as 'confirmed'
        Otherwise:
            - Log an exception to chatter
            - Set all payslips to draft
        """
        self.state = 'confirmed'
        self.payslip_ids.action_confirm()
        self._follow_after_running_payroll()

        if self._check_positive_net_pay():
            # Do not send email if this is a historical period
            if not self.is_history:
                self._send_notification_to_followers()
        else:
            self.button_draft()

    def button_confirm(self):
        self.ensure_one()
        self._check_run_payroll()
        self._confirm_immediately()

    def button_draft(self):
        self.ensure_one()
        self.state = 'draft'
        self.payslip_ids.action_draft()

    def button_done(self):
        def post_je_compensation(payslip):
            employee_id = payslip.employee_id
            payment_method = payslip.payment_method

            # GROSS PAY: DEBIT
            # Debit to Advance Payment account if set on Compensation, otherwise Expense account
            total_advance = 0
            for comp in payslip.compensation_ids:
                account_receivable_id = comp.compensation_id.get_journal_entry_account(employee_id)[0]
                if account_receivable_id:
                    total_advance += comp.amount
                    dict_key = 'advance_{}_{}'.format(employee_id.id, account_receivable_id.id)
                    self._update_ee_data(ee_data, account_receivable_id.id, 'debit', self.pay_date,
                                         '{}'.format(employee_id.name), comp.amount, dict_key=dict_key)

            balance = float_round(payslip.gross_pay - total_advance, precision_digits=2)
            if not float_is_zero(balance, precision_digits=2):
                self._update_ee_data(ee_data, payroll_expense_id.id, 'debit', self.pay_date,
                                     'Gross Pay', balance, dict_key='gross_pay')

            # NET PAY: CREDIT
            if payment_method == 'deposit':
                self._update_ee_data(ee_data, bank_account_id.id, 'credit', self.pay_date,
                                     'Net Pay - Direct Deposit', payslip.net_pay, dict_key='direct_deposit')
            else:
                dict_key = '{}_{}'.format(bank_account_id.id, employee_id.id)
                partner_id = employee_id.address_home_id and employee_id.address_home_id.id or False
                self._update_ee_data(ee_data, bank_account_id.id, 'credit', self.pay_date,
                                     'Net Pay - {} - Check'.format(employee_id.name), payslip.net_pay, dict_key=dict_key, partner_id=partner_id)

        def post_je_deduction(payslip):
            # DEDUCTION
            for line in payslip.deduction_ids:
                deduction_id = line.deduction_id
                label = line.label

                # Employee Deduction: CREDIT
                account_id = deduction_id.ee_account_payable_id.id
                dict_key = 'ded_{}'.format(str(deduction_id.id))
                self._update_ee_data(ee_data, account_id, 'credit', self.pay_date, label, line.amount, dict_key=dict_key)

                # Employer Deduction Contribution: Debit Expense, Credit Payable
                if line.has_company_contribution and line.er_dollar_amt:
                    expense_id = deduction_id.er_expense_account_id.id
                    payable_id = deduction_id.er_account_payable_id.id
                    er_amount = line.er_dollar_amt
                    self._update_er_data(er_data, expense_id, payable_id, self.pay_date, label, er_amount, dict_key=dict_key)

        def post_je_tax(payslip):
            # TAX
            for tax_line in payslip.tax_ids:
                tax_id = tax_line.payroll_tax_id
                amount = tax_line.tax_amt
                label = tax_id.label
                account_vals = {'name': label, 'is_er_tax': tax_line.is_er_tax, 'company_id': self.company_id.id}

                # Employer Tax: Debit Expense, Credit Payable
                if tax_line.is_er_tax:
                    er_account_list = tax_id.get_journal_entry_account(payslip.employee_id, is_er_tax=True)
                    payable_id = er_account_list[0]
                    expense_id = er_account_list[1]
                    if not (expense_id and payable_id):
                        tax_id._create_payroll_account(account_vals)
                        expense_id = tax_id.er_expense_account_id
                        payable_id = tax_id.er_account_payable_id
                    dict_key = 'tax_{}_{}_{}'.format(tax_id, payable_id.id, expense_id.id)
                    self._update_er_data(er_data, expense_id.id, payable_id.id, self.pay_date, label, amount, dict_key=dict_key)

                # Employee Tax: CREDIT
                else:
                    er_account_list = tax_id.get_journal_entry_account(payslip.employee_id)
                    tax_account_id = er_account_list[0]
                    if not tax_account_id:
                        tax_id._create_payroll_account(account_vals)
                        tax_account_id = tax_id.ee_account_payable_id
                    dict_key = 'tax_{}_{}'.format(tax_id, tax_account_id.id)
                    self._update_ee_data(ee_data, tax_account_id.id, 'credit', self.pay_date, label, amount, dict_key=dict_key)

        def create_je_for_employees(aml_ids):
            aml_ids.extend([(0, 0, ee_data[key]) for key in ee_data])

        def create_je_for_company(aml_ids):
            for key in er_data:
                data = er_data[key]
                amount = data['amount']
                date = data['date']
                name = data['name']

                aml_ids.extend([
                    (0, 0, {
                        'account_id': data['debit_account_id'],
                        'debit': amount,
                        'credit': 0,
                        'date': date,
                        'name': name,
                    }),
                    (0, 0, {
                        'account_id': data['credit_account_id'],
                        'debit': 0,
                        'credit': amount,
                        'date': date,
                        'name': name,
                    })])

        self.ensure_one()

        if any(payslip.net_pay < 0 for payslip in self.payslip_ids):
            raise UserError(_('Make sure all payslips have positive net pay then try again.'))

        payroll_journal_id, payroll_expense_id, bank_account_id = self._check_account_config()

        move_line_ids = []  # move lines to be created
        ee_data = {}  # data for employee (salary, tax, deduction)
        er_data = {}  # data for company (tax, contribution)

        # Update Accumulated amount
        self.payslip_ids._calculate_accumulated_amount(tax=True, compout=True)

        for payslip in self.payslip_ids:
            post_je_compensation(payslip)
            post_je_tax(payslip)
            post_je_deduction(payslip)

        # JE for all employee payslips
        create_je_for_employees(move_line_ids)

        # JEs for company (tax, contribution)
        create_je_for_company(move_line_ids)

        account_move = self.env['account.move'].sudo().create({
            'journal_id': payroll_journal_id.id,
            'line_ids': move_line_ids,
            'date': self.pay_date,
            'ref': self.name,
        })
        # If only 1 partner_id is set in all aml of this JE, Odoo automatically assigns that partner for this JE.
        account_move.partner_id = False

        self.write({
            'move_id': account_move.id,
            'state': 'done',
        })
        self.move_id.action_post()

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success!'),
                'type': 'success',
                'message': _('All payslips in this period have been posted journal entries.'),
                'next': {'type': 'ir.actions.act_window_close'},
            }
        }

    def button_history_done(self):
        self.ensure_one()
        self.payslip_ids._calculate_accumulated_amount(tax=True, compout=True)
        self.payslip_ids._calculate_net_pay_history_done()
        self.state = 'done'

    def button_generate_ach_file(self):
        """
        Button to generate ACH file.
        :return: url_action
        """
        self.ensure_one()
        self._check_ach_info()
        return self.env.ref('l10n_us_hr_payroll.ach_template').report_action(self)

    def button_open_compensation(self):
        self.ensure_one()
        open_report_record = self.env['open.payroll.report.wizard'].create({
            'pay_period_id': self.id,
            'report_type': 'Compensation',
        })
        return {
            'type': 'ir.actions.act_window',
            'name': 'Compensation',

            'view_mode': 'form',
            'res_id': open_report_record.id,
            'res_model': 'open.payroll.report.wizard',
            'target': 'new',
        }

    def button_open_deduction(self):
        self.ensure_one()
        open_report_record = self.env['open.payroll.report.wizard'].create({
            'pay_period_id': self.id,
            'report_type': 'Deduction',
        })
        return {
            'type': 'ir.actions.act_window',
            'name': 'Deduction',

            'view_mode': 'form',
            'res_id': open_report_record.id,
            'res_model': 'open.payroll.report.wizard',
            'target': 'new',
        }

    def button_open_tax(self):
        self.ensure_one()
        open_report_record = self.env['open.payroll.report.wizard'].create({
            'pay_period_id': self.id,
            'report_type': 'Taxes',
        })
        return {
            'type': 'ir.actions.act_window',
            'name': 'Taxes',

            'view_mode': 'form',
            'res_id': open_report_record.id,
            'res_model': 'open.payroll.report.wizard',
            'target': 'new',
        }

    def button_open_move_id(self):
        self.ensure_one()
        action = self.env.ref('account.action_move_journal_line').read()[0]
        action['views'] = [(self.env.ref('account.view_move_form').id, 'form')]
        action['res_id'] = self.move_id.id

        return action

    ####################################################################################################################
    # CRUD
    ####################################################################################################################
    def init_scheduled_payslips(self):
        """
        Init all payslips for a new scheduled payroll.
        """
        if self and self.pay_type == 'frequency' and self.pay_frequency_id:
            employee_ids = self.env['hr.employee'].search([
                ('pay_frequency_id', '=', self.pay_frequency_id.id),
                ('company_id', '=', self.company_id.id)
            ])
            # Must check employee_ids first because :meth:`copy_payroll_data` always returns value
            # even if employee_ids is False, or an error (unique pay frequency) will be raised.
            if employee_ids:
                payroll_data = employee_ids.copy_payroll_data(incl_comp=True, incl_deduc=True)
                self.write({'payslip_ids': [(0, 0, line) for line in payroll_data]})

    @api.model
    def create(self, vals):
        res = super(PayPeriod, self).create(vals)
        if res.pay_type == 'frequency':
            res.init_scheduled_payslips()

        return res

    def write(self, vals):
        # Reset all working hours and paid leaves if user remove period.
        if not vals.get('start_date', True) or not vals.get('end_date', True):
            self.reset_all_hours()

        return super(PayPeriod, self).write(vals)

    def unlink(self):
        if self.filtered(lambda r: r.state in ['confirmed', 'done']):
            raise UserError(_('Cannot delete period(s) being confirmed or done.'))

        if self.mapped('payslip_ids'):
            raise UserError(_('Remove all payslips inside before deleting period(s).'))

        return super(PayPeriod, self).unlink()

    ####################################################################################################################
    # HELPER METHODS
    ####################################################################################################################
    def _get_missing_employees_domain(self):
        self.ensure_one()
        return [
            ('pay_frequency_id', '=', self.pay_frequency_id.id),
            ('id', 'not in', self.payslip_ids.mapped('employee_id').ids)
        ]

    def _update_total_period_data(self):
        """
        Update total working time, payroll cost when a period is set to 'done'.
        Used to query on Dashboard.
        """
        for record in self:
            payslip_ids = record.payslip_ids
            if payslip_ids:
                record.total_regular = sum(payslip_ids.mapped('regular'))
                record.total_overtime = sum(payslip_ids.mapped('overtime'))
                record.total_double = sum(payslip_ids.mapped('double_overtime'))
                record.total_holiday = sum(payslip_ids.mapped('holiday'))
                record.total_er_tax = sum(payslip_ids.mapped('total_er_tax'))
                record.total_er_deduction = sum(payslip_ids.mapped('total_er_deduction'))

    def get_all_hours(self):
        self.mapped('payslip_ids').get_all_hours()

    def reset_all_hours(self):
        self.mapped('payslip_ids').reset_all_hours()

    def _update_ee_data(self, data, account_id, amount_field, date, name, amount, dict_key, partner_id=False):
        """
        This function is use to update move line data to create JE, because we need to sum amount.
        Each key is one move line in one big JE.

        :param data: the data dictionary
        :param account_id: account_id to put amount into
        :param amount_field: debit or credit side
        :param date: date, most likely to be pay date
        :param name: move line label
        :param amount: dollar amount
        :param dict_key: group by dict_key
        :param partner_id: employee_id
        :return:
        """
        if dict_key not in data:
            data[dict_key] = {
                'account_id': account_id,
                'debit': 0,
                'credit': 0,
                'date': date,
                'name': name,
                'partner_id': partner_id
            }

        agg_amount = data[dict_key].get(amount_field, 0)
        data[dict_key][amount_field] = agg_amount + amount

    def _update_er_data(self, data, debit_account_id, credit_account_id, date, name, amount, dict_key):
        """
        This function is use to update move line data for employer. Each key is one separate JE.
        """
        if dict_key not in data:
            data[dict_key] = {
                'debit_account_id': debit_account_id,
                'credit_account_id': credit_account_id,
                'amount': 0,
                'date': date,
                'name': name,
            }

        agg_amount = data[dict_key].get('amount', 0)
        data[dict_key]['amount'] = agg_amount + amount

    def _follow_after_running_payroll(self):
        uid = self.env.user.partner_id.id
        self.message_subscribe([uid])

    def _send_notification_to_followers(self):
        """
        Send email to followers after running payroll.
        """
        self.ensure_one()
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        action = self.env.ref(PERIOD_ACTION_VIEW.get(self.pay_type)).id
        menu_id = self.env.ref(MENU_VIEW).id
        # Button link to this pay period in mail body.
        action_url = '{}/web#id={}&action={}&model={}&view_type={}&menu_id={}'.format(base_url, self.id, action, self._name, 'form', menu_id)
        template_ctx = {'action_url': action_url}

        mail_template = self.env.ref('l10n_us_hr_payroll.mail_template_pay_period_confirmed')
        # Create mail (if force_send=True -> Send immediately)
        mail_id = mail_template.with_context(**template_ctx).send_mail(
            res_id=self.id,
            force_send=False,
            raise_exception=False,
            notif_layout='l10n_us_hr_payroll.mail_layout_pay_period_confirmed'
        )
        mail = self.env['mail.mail'].browse(mail_id)
        if mail:
            # Add recipient (followers) and send.
            mail.recipient_ids = [(6, 0, self.message_partner_ids.ids)]
            mail.send()

    def _check_ach_info(self):
        # Check data before generating ACH header.
        company_id = self.env.company
        bank_journal = company_id.bank_account_id
        res_partner_bank = bank_journal.bank_account_id
        res_bank = bank_journal.bank_id

        if not (
            bank_journal and bank_journal.type == 'bank' and
            res_partner_bank and res_partner_bank.acc_number and res_partner_bank.aba_routing and
            res_bank and res_bank.name and res_bank.immediate_org
        ):
            raise UserError(_("Please make sure Bank Account information has been set "
                              "in Payroll > Configuration > Settings > Payroll Account and try again."))

        if not company_id.vat:
            raise UserError(_("Please make sure Company's Tax ID have been set "
                              "in Settings > Company Set Up > General Information and try again."))

    def _generate_ach_header(self):
        """
        Generate header of ACH file, include: routing number, bank name, company name, tax ID
        Ref: https://help.imscre.net/hc/en-us/articles/360000402343-NACHA-Setup#:~:text=ACH%20Immediate%20Origin,originate%20ACH%20files%20through%20them.
        :return: header
        """
        self._check_ach_info()

        company_id = self.env.company
        bank_journal = company_id.bank_account_id
        res_partner_bank = bank_journal.bank_account_id
        res_bank = bank_journal.bank_id

        return {
            'immediate_dest': res_partner_bank.aba_routing,
            'immediate_org': res_bank.immediate_org,
            'immediate_dest_name': res_bank.name,
            'immediate_org_name': company_id.name,
            'company_id': '1' + company_id.vat
        }

    def generate_ach_file(self):
        """
        Generate ACH file after period is set to 'done'.
        Print all payment information in payslips having payment_method = 'deposit'.
        """
        self.ensure_one()
        company_id = self.env.company
        last_print_date = company_id.last_print_date
        last_print_file_id = company_id.last_print_file_id

        today = fields.Date.today()
        # File ID is from 'A' to 'Z', should be 'A' for the first of the day, 'B' for the second and so on.
        if not last_print_date or last_print_date != today:
            company_id.last_print_date = today
            company_id.last_print_file_id = file_id = 'A'
        else:
            company_id.last_print_file_id = file_id = chr(
                ord(last_print_file_id) + 1) if last_print_file_id != 'Z' else 'A'

        header = self._generate_ach_header()
        ach_file = AchFile(file_id, header)
        entries = self.payslip_ids._generate_ach_ppd_entries()
        # Payment_type = 'outbound' => credits=True, debits=False
        ach_file.add_batch('PPD', entries, credits=True, debits=False)
        return ach_file

    def get_ach_file_content(self):
        # Use for ir.actions.server
        self.ensure_one()
        ach_file = self.generate_ach_file()
        return ach_file.render_to_string()

    ####################################################################################################################
    # CHECK DATA FOR RUNNING PAYROLL
    ####################################################################################################################
    def _check_run_payroll_confirmed(self):
        """
        Raise error message if there is another pay period in Confirmed state.
        """
        confirmed = self.sudo().search([('company_id', '=', self.company_id.id),
                                        ('state', '=', 'confirmed')])
        if confirmed:
            raise UserError(_('Another period ({}) is still in Confirmed state. '
                              'You need to mark it as Done or set it back to Draft before confirming this period.'.format(confirmed[0].name)))

    def _check_run_payroll_empty(self):
        """
        Raise error message if there is no payslip in this period.
        """
        if not self.payslip_ids:
            raise UserError(_('Please add at least one Payslip.\n'))

    def _check_run_payroll_geocode(self):
        """
        Raise error message if no geocode/work_geocode.
        """
        need_action_address = self.payslip_ids.filtered(lambda x: not x.geocode or not x.work_geocode)

        if need_action_address:
            names = '- ' + '\n- '.join(a.employee_id.name for a in need_action_address)
            raise UserError(_("""The work/mailing addresses of these employees are missing or incorrect:
            {}
            Please update in the employee form and click Update Information on their payslip.\n
            """).format(names))

    def _check_run_payroll_update_period(self):
        """
        Update 'number_periods' and 'current_period' for this period.
        Raise error message if errors related to 'frequency_id'.
        """
        pay_frequency_id = self.pay_frequency_id

        if self.is_history:
            number_periods = 52
            current_period = 1
        else:
            number_periods = pay_frequency_id.frequency

            if self.pay_type == 'frequency':
                current_period = calculate_current_period(pay_frequency_id, self.pay_date)
            else:
                # Get the current period from the last pay period having state in ['done']
                query = """
                SELECT current_period
                FROM pay_period
                WHERE state = 'done' AND pay_frequency_id = {}
                ORDER BY pay_date DESC
                LIMIT 1;
                """.format(pay_frequency_id.id)
                self.env.cr.execute(query)
                res = self.env.cr.fetchall()
                current_period = res[0][0] if res else 1

        self.write({
            'number_periods': number_periods,
            'current_period': current_period
        })

    def _check_run_payroll(self):
        """
        Check before running payroll and raise warning if any error.
        """
        self.ensure_one()
        self._check_run_payroll_confirmed()
        self._check_run_payroll_empty()
        self._check_unique_frequency()
        self._check_standard_working_hours()
        self._check_run_payroll_geocode()
        self._check_run_payroll_update_period()

    def _check_period_date(self):
        """
        For pay_type != Bonus and not historical period (Off-cycle).
        To be sure that start_date and end_date exist before getting working hours/leave days.
        """
        self.ensure_one()
        if not (self.pay_type == 'bonus' or self.is_history or (self.start_date and self.end_date)):
            raise UserError(_('Please add Start Date and End Date for this Pay Period.'))

    def _check_time_tracking_rule(self):
        """
        Check time_tracking_id of all payslips before getting working hours.
        :raise: UserError
        """
        self.ensure_one()
        names = ''
        payslip_ids = self.payslip_ids.filtered(lambda r: r.employee_type != 'salary' and not r.time_tracking_id)
        if payslip_ids:
            for record in payslip_ids:
                names += '- ' + record.employee_id.name + '\n'
            raise UserError(_("""These employees need to be set Overtime Rule to get working hours:
            {}Please check their profiles, then click 'Update Information' and try again.""".format(names)))

    def _check_standard_working_hours(self):
        """
        Check resource_calendar_id (standard working hours per week) before update compensation list.
        :raise: UserError
        """
        self.ensure_one()
        names = ''
        payslip_ids = self.payslip_ids.filtered(lambda r: not r.resource_calendar_id)
        if payslip_ids:
            for record in payslip_ids:
                names += '- ' + record.employee_id.name + '\n'
            raise UserError(_("""These employees need to be set Standard Working Hours:
            {}Please check their profiles, then click 'Update Information' and try again.""".format(names)))

    def _check_account_config(self):
        """
        Check if payroll account info is missing in config setting and in deduction.
        """
        payroll_journal_id = self.env.company.payroll_journal_id
        bank_journal_id = self.env.company.bank_account_id
        payroll_expense_id = self.env.company.payroll_expense_account_id

        if not (payroll_journal_id and bank_journal_id and payroll_expense_id):
            raise UserError(_("Please make sure Payroll Account information is set in "
                              "'Payroll > Configuration > Settings > Payroll Account' and try again."))

        deduction_ids = self.mapped('payslip_ids.deduction_ids.deduction_id')
        names = ''
        for record in deduction_ids:
            vertex_id = record.vertex_id
            account_id = record.ee_account_payable_id
            expense_id = record.er_expense_account_id
            payable_id = record.er_account_payable_id
            # not vertex_id => only need account_id
            if not (account_id and (not vertex_id or expense_id and payable_id)):
                names += '- ' + record.name + '\n'
        if names:
            raise UserError(_("""These Deductions are missing Payroll Account information:
{}Please make sure all of them are set in 'Payroll > Configuration > Deduction' and try again.
            """.format(names)))

        bank_account_id = bank_journal_id.default_account_id
        return payroll_journal_id, payroll_expense_id, bank_account_id

    def _check_positive_net_pay(self):
        """
        After confirming period, check if any payslip has net pay < 0 -> add an exception activity to this period
        :return: True if all payslips have positive net pay, otherwise return False
        """
        self.ensure_one()
        errors = ''
        for payslip in self.payslip_ids.filtered(lambda r: r.net_pay < 0):
            payslip.is_negative_net_pay = True
            errors += '<li>{}: <b>Net Pay = {}</b></li>'.format(payslip.employee_id.name, payslip._format_currency_amount(payslip.net_pay))

        if errors:
            self.activity_schedule(
                'mail.mail_activity_data_warning',
                note="""<div>Exception(s):<ul>{}</ul></div>""".format(errors),
                summary=_('Cannot process period!'),
                user_id=self.env.user.id)
            return False
        return True

    ####################################################################################################################
    # EXPORT/IMPORT PAYROLL HISTORICAL DATA
    ####################################################################################################################
    def _export_payslip_data_template(self, name, view_id):
        """
        Open export wizard form to add data into payslips.
        :param name: action name
        :param view_id: compensation/deduction
        :return: action
        """
        self.ensure_one()
        wizard = self.env['export.historical.data.wizard'].create({'period_id': self.id, 'name': name})
        action = {
            'name': name,
            'type': 'ir.actions.act_window',
            'res_model': 'export.historical.data.wizard',
            'res_id': wizard.id,
            'view_mode': 'form',
            'view_id': view_id.id,
            'context': {'form_view_initial_mode': 'edit'},
            'target': 'current',
        }
        return action

    def button_export_payslip_compensation(self):
        """
        Open 'Export Compensations' form to add compensations into payslips.
        :return: action
        """
        name = _('Export Compensations')
        view_id = self.env.ref('l10n_us_hr_payroll.export_historical_data_wizard_view_compensation')
        return self._export_payslip_data_template(name, view_id)

    def button_import_payslip_compensation(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.client',
            'tag': 'import',
            'params': {
                'model': 'payslip.compensation',
                'context': self.env.context.copy()
            }
        }

    def button_export_payslip_deduction(self):
        """
        Open 'Export Deductions' form to add deductions into payslips.
        :return: action
        """
        name = _('Export Deductions')
        view_id = self.env.ref('l10n_us_hr_payroll.export_historical_data_wizard_view_deduction')
        return self._export_payslip_data_template(name, view_id)

    def button_import_payslip_deduction(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.client',
            'tag': 'import',
            'params': {
                'model': 'payslip.deduction',
                'context': self.env.context.copy()
            }
        }

    def button_export_payslip_tax(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': '/period_export_payslip_tax/{}'.format(self.id),
            'target': 'current',
        }

    def button_import_payslip_tax(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.client',
            'tag': 'import',
            'params': {
                'model': 'payslip.tax',
                'context': self.env.context.copy()
            }
        }
