import base64
from datetime import date
from PyPDF2 import PdfFileReader, PdfFileWriter

from odoo import api, fields, models, tools, _
from odoo.addons.l10n_us_hr_payroll.utils.utils import convert_time_zone
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT as DF
from odoo.tools.misc import formatLang, format_date
from odoo.exceptions import UserError


class PayrollPayslip(models.Model):
    _inherit = 'payroll.payslip'

    check_number = fields.Char(string="Check Number", copy=False, index=True, group_operator=None)
    check_date = fields.Datetime(string='Check Date', copy=False)

    def print_check_paystub(self):
        """
        Print Checks/Paystubs for chosen payslips.
        """
        if self._context.get('check', False):
            return self.print_checks()
        if self._context.get('paystub', False):
            return self.print_separated_stubs()

    def print_checks(self):
        def _check_int(payslip):
            try:
                return int(payslip.check_number)
            except ValueError:
                return 0

        if any(payslip.payment_method != 'check' or payslip.state != 'done' for payslip in self):
            raise UserError(_("Payslips to print as a checks must have 'Check' selected as payment method and current status must be 'Done'"))

        # The wizard asks for the number printed on the pre-printed check
        printed_checks = self.search([
            ('check_number', '!=', False)
        ]).sorted(key=_check_int, reverse=True)

        next_check_number = printed_checks and _check_int(printed_checks[0]) + 1 or 1
        context = self._context.copy()
        context.update({
            'payslip_ids': self.ids,
            'default_next_check_number': next_check_number,
        })

        return {
            'name': 'Print Pre-numbered Checks',
            'type': 'ir.actions.act_window',
            'res_model': 'print.prenumbered.checks',
            'view_mode': 'form',
            'target': 'new',
            'context': context
        }

    def print_separated_stubs(self):
        paystub_template = self._get_separated_stub_template()
        return paystub_template.report_action(self)

    ####################################################################################################################
    # CHECK PRINTING METHODS
    ####################################################################################################################
    def do_print_check(self):
        if not self:
            return

        company_id = self[0].company_id
        check_layout = company_id.account_check_printing_layout

        if not check_layout or check_layout == 'disabled':
            raise UserError(_('Please go to Accounting > Configuration > Settings > Vendor Payments and select a check layout, then try again.'))

        if company_id.country_id.code == 'US' or bool(self.env['ir.config_parameter'].sudo().get_param('account_check_printing_force_us_format')):
            layout_external_id = check_layout.split('.')[1]
            report_id = self.env.ref('l10n_us_payroll_check_printing.{}'.format(layout_external_id))

            if self._context.get('paystub', False):
                data_ctx = {'options': {'check_paystub': True, 'docids': self.ids}}
                return report_id.report_action(self, data=data_ctx)
            return report_id.report_action(self)

        return super().do_print_check()

    @api.model
    def _check_fill_line(self, amount_str):
        return amount_str and (amount_str + ' ').ljust(200, '*') or ''

    @api.model
    def _check_ssn_id(self, ssnid):
        return ssnid and 'XXX-XX-' + ssnid[-4:] or ''

    def _calculate_ytd_net_pay(self):
        self.ensure_one()
        pay_period_id = self.pay_period_id
        pay_date = pay_period_id.pay_date
        year = pay_date.year
        payslips = self.search([
            ('employee_id', '=', self.employee_id.id),
            ('pay_period_id.pay_date', '>=', date(year, 1, 1).strftime(DF)),
            ('pay_period_id.pay_date', '<=', pay_date.strftime(DF)),
            ('pay_period_id.state', '=', 'done'),
        ])
        ytd_net_pay = payslips and sum(payslips.mapped('net_pay')) or 0.0
        return ytd_net_pay

    def _check_build_page_info(self, stub_lines):
        self.ensure_one()
        env = self.env
        len_stub_lines = len(stub_lines)
        net_pay_in_words = self.currency_id.amount_to_text(self.net_pay) if self.currency_id else ''
        employee_id = self.employee_id
        end_date = self.pay_period_id and self.pay_period_id.end_date
        ytd_net_pay = self._calculate_ytd_net_pay()
        return {
            'payment_date': format_date(env, self.pay_period_id.pay_date),
            'employee_number': employee_id.id,
            'employee_name': employee_id.name,
            'ssnid': self._check_ssn_id(employee_id.ssnid),
            'end_date': format_date(env, end_date),
            'check_number': self.check_number,
            'department': employee_id.department_id and employee_id.department_id.name or '',
            'currency': self.currency_id,
            'net_pay': formatLang(env, self.net_pay, currency_obj=self.currency_id) if len_stub_lines != 0 else 'VOID',
            'net_pay_in_words': self._check_fill_line(net_pay_in_words) if len_stub_lines != 0 else 'VOID',
            # Pay Rate information
            'pay_rate': formatLang(env, self.pay_rate, currency_obj=self.currency_id),
            'gross_pay': formatLang(env, self.gross_pay, currency_obj=self.currency_id),
            'total_ee_deduction': formatLang(env, self.total_ee_deduction, currency_obj=self.currency_id),
            'ytd_compensations': formatLang(env, self.compensation_ids and sum(self.compensation_ids.mapped('ytd_amount')) or 0.0, currency_obj=self.currency_id),
            'ytd_deduction': formatLang(env, self.deduction_ids and sum(self.deduction_ids.mapped('ytd_amount')) or 0.0, currency_obj=self.currency_id),
            'ytd_net_pay': formatLang(env, ytd_net_pay, currency_obj=self.currency_id),
            # Remove stub_lines - PAYROLL-85: now we print check and stub separately!
            # Stub lines
            # 'stub_lines': stub_lines,
        }

    def _check_get_pages(self):
        """ Returns the data structure used by the template : a list of dicts containing what to print on pages.
        """
        self.ensure_one()
        pages = []
        for payslip in self:
            stub_lines = self._make_stub_lines()
            pages.append(self._check_build_page_info(stub_lines))
        return pages

    def _make_stub_lines(self, no_leaves=False):
        self.ensure_one()
        currency_id = self.currency_id
        env = self.env
        stub_lines = []
        # Compensations & deductions
        compensations = self.compensation_ids
        deductions = self.deduction_ids
        if len(deductions) > len(compensations):
            for deduction in deductions:
                compensation = compensations and compensations[0] or False
                if compensation:
                    stub_lines.append([
                        compensation.label,
                        compensation.hours,
                        formatLang(env, compensation.amount, currency_obj=currency_id),
                        formatLang(env, compensation.ytd_amount, currency_obj=currency_id),
                        deduction.label,
                        formatLang(env, deduction.amount, currency_obj=currency_id),
                        formatLang(env, deduction.ytd_amount, currency_obj=currency_id),
                    ])
                    compensations -= compensation
                else:
                    stub_lines.append([
                        '',
                        '',
                        '',
                        '',
                        deduction.label,
                        formatLang(env, deduction.amount, currency_obj=currency_id),
                        formatLang(env, deduction.ytd_amount, currency_obj=currency_id),
                    ])
        else:
            for compensation in compensations:
                deduction = deductions and deductions[0] or False
                if deduction:
                    stub_lines.append([
                        compensation.label,
                        compensation.hours,
                        formatLang(env, compensation.amount, currency_obj=currency_id),
                        formatLang(env, compensation.ytd_amount, currency_obj=currency_id),
                        deduction.label,
                        formatLang(env, deduction.amount, currency_obj=currency_id),
                        formatLang(env, deduction.ytd_amount, currency_obj=currency_id),
                    ])
                    deductions -= deduction
                else:
                    stub_lines.append([
                        compensation.label,
                        compensation.hours,
                        formatLang(env, compensation.amount, currency_obj=currency_id),
                        formatLang(env, compensation.ytd_amount, currency_obj=currency_id),
                        '',
                        '',
                        '',
                    ])
        # Leaves
        leaves = self.payroll_vacation_ids
        compensation_holiday_id = self.env.ref('l10n_us_hr_payroll.payroll_compensation_holiday')
        for leave in leaves:
            if leave.payroll_compensation_id == compensation_holiday_id:
                continue
            stub_lines.append([
                leave.payroll_compensation_id.name,
                leave.remaining_leave_days,
                '',
                '',
                '',
                '',
                '',
            ])
        return stub_lines

    @staticmethod
    def group_lines(result, rec_id, new_line, ytd):
        """
        Group compensations/deductions into list of multiple groups based on their compensation_id, deduction_id.
        :param result: list of dict to pass to xml report.
        :param rec_id: id of compensation/deduction record.
        :param new_line: list of values to show on paystub for each compensation/deduction.
        :param ytd: YTD amount of this new line.
        :return: total YTD.
        """
        def append_new_group():
            result.append({
                'id': rec_id,
                'lines': [new_line],
                'ytd': ytd
            })

        if not result:
            append_new_group()
        else:
            group = {}
            for _group in result:
                if _group['id'] == rec_id:
                    group = _group
                    break
            if group:
                group['lines'].append(new_line)
                group['ytd'] = max(group['ytd'], ytd)
            else:
                append_new_group()

    ####################################################################################################################
    # SEPARATED PAYSTUB
    ####################################################################################################################
    # Compensations ----------------------------------------------------------------------------------------------------
    def get_historical_compensation_lines(self, lines):
        """
        Find all historical compensations in current years, excepts the ones whose compensation type is in current payslip.
        :param lines: list containing dictionary of each compensation value.
        """
        self.ensure_one()
        query = """
                    SELECT DISTINCT ON (compensation_id) id
                    FROM payslip_compensation
                    WHERE
                        employee_id = %s AND
                        pay_date BETWEEN %s AND %s AND
                        compensation_id NOT IN %s
                    ORDER BY compensation_id, pay_date DESC, sequence;
                """
        self._cr.execute(query, [self.employee_id.id,
                                 fields.Date.to_string(self.pay_date.replace(day=1, month=1)),
                                 fields.Date.to_string(self.pay_date),
                                 tuple(self.compensation_ids.mapped('compensation_id').ids or [-1])])

        old_compensation_ids = self.env['payslip.compensation'].browse([data[0] for data in self._cr.fetchall()])

        for compensation in old_compensation_ids.sorted(key=lambda r: r.sequence):
            line = [compensation.label, '_', '_', '_']
            self.group_lines(lines, compensation.compensation_id.id, line, compensation.ytd_amount)

    def get_current_compensation_lines(self, lines):
        """
        Find all compensations in current payslip.
        :param lines: list containing dictionary of each compensation value.
        """
        self.ensure_one()
        env = self.env
        currency_id = self.currency_id

        for compensation in self.compensation_ids.sorted(key=lambda r: r.sequence):
            line = [
                compensation.label,
                '{:,.2f}'.format(compensation.hours),
                formatLang(env, compensation.rate, currency_obj=currency_id),
                formatLang(env, compensation.amount, currency_obj=currency_id),
            ]
            self.group_lines(lines, compensation.compensation_id.id, line, compensation.ytd_amount)

    def get_compensation_lines(self):
        self.ensure_one()
        env = self.env
        currency_id = self.currency_id
        total_ytd = 0

        compensation_lines = []
        self.get_current_compensation_lines(compensation_lines)
        if self.company_id.include_historical_paystub:
            self.get_historical_compensation_lines(compensation_lines)

        for group in compensation_lines:
            total_ytd += group['ytd']
            group['ytd'] = formatLang(env, group['ytd'], currency_obj=currency_id)

        return compensation_lines, total_ytd

    # Deductions & Taxes -----------------------------------------------------------------------------------------------
    def get_historical_deduction_lines(self, lines, er_lines):
        """
        Find all historical deductions in current years, excepts the ones whose deduction type is in current payslip.
        :param lines: list containing dictionary of each deduction value.
        :param er_lines: list containing dictionary of each company contribution value.
        """
        self.ensure_one()
        query = """
                    SELECT DISTINCT ON (deduction_id) id
                    FROM payslip_deduction
                    WHERE
                        employee_id = %s AND
                        pay_date BETWEEN %s AND %s AND
                        deduction_id NOT IN %s
                    ORDER BY deduction_id, pay_date DESC;
                """
        self._cr.execute(query, [self.employee_id.id,
                                 fields.Date.to_string(self.pay_date.replace(day=1, month=1)),
                                 fields.Date.to_string(self.pay_date),
                                 tuple(self.deduction_ids.mapped('deduction_id').ids or [-1])])

        old_deduction_ids = self.env['payslip.deduction'].browse([data[0] for data in self._cr.fetchall()])

        for deduction in old_deduction_ids.sorted(key=lambda r: r.label):
            line = [deduction.label, '_']
            self.group_lines(lines, deduction.deduction_id.id, line, deduction.ytd_amount)

            if deduction.er_dollar_amt:
                line = [deduction.label, '_']
                self.group_lines(er_lines, deduction.deduction_id.id, line, deduction.er_ytd_amount)

    def get_current_deduction_lines(self, lines, er_lines):
        """
        Find all deductions in current payslip.
        :param lines: list containing dictionary of each deduction value.
        :param er_lines: list containing dictionary of each company contribution value.
        """
        self.ensure_one()
        env = self.env
        currency_id = self.currency_id

        for deduction in self.deduction_ids.sorted(key=lambda r: r.label):
            line = [
                deduction.label,
                formatLang(env, deduction.amount, currency_obj=currency_id),
            ]
            self.group_lines(lines, deduction.deduction_id.id, line, deduction.ytd_amount)

            if deduction.er_dollar_amt:
                line = [
                    deduction.label,
                    formatLang(env, deduction.er_dollar_amt, currency_obj=currency_id),
                ]
                self.group_lines(er_lines, deduction.deduction_id.id, line, deduction.er_ytd_amount)

    def get_historical_tax_lines(self, lines):
        """
        Find all historical taxes in current years, excepts the ones whose tax type is in current payslip.
        :param lines: list containing dictionary of each tax value.
        """
        self.ensure_one()
        query = """
                    SELECT DISTINCT ON (payroll_tax_id) id
                    FROM payslip_tax
                    WHERE
                        employee_id = %s AND
                        pay_date BETWEEN %s AND %s AND
                        payroll_tax_id NOT IN %s AND
                        NOT is_er_tax
                    ORDER BY payroll_tax_id, pay_date DESC;
                """
        self._cr.execute(query, [self.employee_id.id,
                                 fields.Date.to_string(self.pay_date.replace(day=1, month=1)),
                                 fields.Date.to_string(self.pay_date),
                                 tuple(self.tax_ids.mapped('payroll_tax_id').ids or [-1])])

        old_tax_ids = self.env['payslip.tax'].browse([data[0] for data in self._cr.fetchall()])

        for tax in old_tax_ids:
            line = [tax.payroll_tax_id.label, '_']
            self.group_lines(lines, tax.payroll_tax_id.id, line, tax.ytd_amount)

    def get_current_tax_lines(self, lines):
        """
        Find all taxes in current payslip
        :param lines: list containing dictionary of each tax value.
        """
        self.ensure_one()
        env = self.env
        currency_id = self.currency_id

        for tax in self.tax_ids.filtered(lambda t: not t.is_er_tax):
            line = [
                tax.payroll_tax_id.label,
                formatLang(env, tax.tax_amt, currency_obj=currency_id),
            ]
            self.group_lines(lines, tax.payroll_tax_id.id, line, tax.ytd_amount)

    def get_deduction_lines(self):
        self.ensure_one()
        currency_id = self.currency_id
        env = self.env
        total_ytd = 0
        total_er_ytd = 0

        deduction_lines = []
        contribution_lines = []
        tax_lines = []
        self.get_current_deduction_lines(deduction_lines, contribution_lines)
        self.get_current_tax_lines(tax_lines)

        if self.company_id.include_historical_paystub:
            self.get_historical_deduction_lines(deduction_lines, contribution_lines)
            self.get_historical_tax_lines(tax_lines)

        result = deduction_lines + tax_lines
        for group in result:
            total_ytd += group['ytd']
            group['ytd'] = formatLang(env, group['ytd'], currency_obj=currency_id)

        for group in contribution_lines:
            total_er_ytd += group['ytd']
            group['ytd'] = formatLang(env, group['ytd'], currency_obj=currency_id)

        return result, total_ytd, contribution_lines, total_er_ytd

    # Leaves -----------------------------------------------------------------------------------------------------------
    def get_leave_lines(self):
        self.ensure_one()
        compensation_holiday_id = self.env.ref('l10n_us_hr_payroll.payroll_compensation_holiday')
        return self.payroll_vacation_ids.filtered(lambda pv: pv.payroll_compensation_id != compensation_holiday_id)

    # PAYSTUB ==========================================================================================================
    def get_stub_info(self):
        self.ensure_one()
        env = self.env
        tz = env.context.get('tz', False) or env.user.tz or 'UTC'
        # Get information
        include_company_contribution = self.env.company.include_company_contribution
        compensation_lines, ytd_compensation = self.get_compensation_lines()
        deduction_lines, ytd_deduction, contribution_lines, er_ytd_deduction = self.get_deduction_lines()
        leave_lines = self.get_leave_lines()
        len_compensation_lines = len(compensation_lines)
        employee_id = self.employee_id
        ytd_net_pay = self._calculate_ytd_net_pay()

        return {
            'name': 'Payslip of {}'.format(employee_id.name),
            'address_home_id': employee_id.address_home_id,
            'employee_code': employee_id.employee_code,
            'employee_name': employee_id.name,
            'ssnid': self._check_ssn_id(employee_id.ssnid),
            'end_date': format_date(env, self.end_date),
            'start_date': format_date(env, self.start_date),
            'payment_method': self.payment_method,
            'pay_date': format_date(env, self.pay_date),
            'check_number': self.check_number,
            'check_date': format_date(env, convert_time_zone(dt=self.check_date, tz=tz)),
            'department': employee_id.department_id and employee_id.department_id.name or '',
            'currency': self.currency_id,
            'net_pay': formatLang(env, self.net_pay, currency_obj=self.currency_id) if len_compensation_lines != 0 else 'VOID',
            # Pay Rate information
            'pay_rate': formatLang(env, self.pay_rate, currency_obj=self.currency_id),
            'gross_pay': formatLang(env, self.gross_pay, currency_obj=self.currency_id),
            'total_ee_deduction': formatLang(env, self.total_ee_deduction + self.total_ee_tax, currency_obj=self.currency_id),
            'total_er_deduction': formatLang(env, self.total_er_deduction, currency_obj=self.currency_id),
            'ytd_compensations': formatLang(env, ytd_compensation, currency_obj=self.currency_id),
            'ytd_deduction': formatLang(env, ytd_deduction, currency_obj=self.currency_id),
            'er_ytd_deduction': formatLang(env, er_ytd_deduction, currency_obj=self.currency_id),
            'ytd_net_pay': formatLang(env, ytd_net_pay, currency_obj=self.currency_id),
            'compensation_lines': compensation_lines,
            'deduction_lines': deduction_lines,
            'contribution_lines': contribution_lines,
            'leave_lines': leave_lines,
            'include_company_contribution': include_company_contribution,
        }

    @api.model
    def _get_separated_stub_template(self):
        return self.env.ref('l10n_us_payroll_check_printing.action_separated_paystub')

    def _get_report_password(self):
        """
        The password of paystub is combination of ssn and birthday
        """
        self.ensure_one()
        employee_id = self.employee_id
        ssnid = employee_id.ssnid
        birthday = employee_id.birthday
        if not ssnid:
            raise UserError(_('Please set up SSN number for "{}"'.format(employee_id.name)))
        if not birthday:
            raise UserError(_('Please set up birthday for "{}"'.format(employee_id.name)))
        birthday_str = birthday.strftime('%m%d%Y')
        last_4_digits_ssn = ssnid[7:]
        return birthday_str + last_4_digits_ssn

    def _set_report_password(self, name, bin_data):
        """
        Param:
        - name (char): report name
        - bin_data (binary): pdf content as binary

        """
        self.ensure_one()
        password = self._get_report_password()
        current_file_pdf = base64.b64decode(bin_data)
        temp_file = open('/tmp/tmp.pdf', 'wb')
        temp_file = temp_file.write(current_file_pdf)
        pdf_file = open('/tmp/tmp.pdf', 'rb')
        pdf_reader = PdfFileReader(pdf_file)
        pdf_writer = PdfFileWriter()

        for pagenum in range(pdf_reader.numPages):
            pdf_writer.addPage(pdf_reader.getPage(pagenum))

        pdf_writer.encrypt(password)
        result_pdf = open('/tmp/' + password, 'wb')
        pdf_writer.write(result_pdf)
        result_pdf.close()
        with open('/tmp/' + password, "rb") as pdf_file:
            encoded_string = base64.b64encode(pdf_file.read())
        return name, encoded_string

    def action_send_paystub(self):
        mail_template = self.env.ref('l10n_us_payroll_check_printing.mail_template_paystub')
        for record in self:
            mail_template.send_mail(res_id=record.id, force_send=False, raise_exception=False)
