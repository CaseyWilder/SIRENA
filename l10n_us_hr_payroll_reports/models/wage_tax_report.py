from datetime import date

from odoo import api, fields, models
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT as DF
from odoo.addons.l10n_us_hr_payroll.utils.vertex import FED_WH_ID, SOC_SEC_EE_ID, SOC_SEC_ER_ID,\
    MED_EE_ID, MED_ER_ID, STATE_WH_ID, COUNTY_WH_ID, CITY_WH_ID, Vertex

# TODO: Local tax is County or City, or both?
TAX_LIST = (FED_WH_ID, SOC_SEC_EE_ID, MED_EE_ID, STATE_WH_ID, COUNTY_WH_ID)


class WageTaxReport(models.Model):
    _name = 'wage.tax.report'
    _description = 'Wage and Tax Statement (W-2)'

    name = fields.Char('Name', compute='_compute_name', store=True)
    year = fields.Char('Year')

    # Employee's Info
    employee_id = fields.Many2one('hr.employee', 'Employee')
    partner_id = fields.Many2one('res.partner', "e. Employee's name, address, and ZIP code")
    ssnid = fields.Char(related='employee_id.ssnid', string='a. Employee’s social security number', store=True)
    is_statutory = fields.Boolean('13. Statutory employee')
    is_retirement_plan = fields.Boolean('13. Retirement plan')
    is_third_party_sick_pay = fields.Boolean('13. Third-party sick pay')

    # Company's Info
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    company_partner_id = fields.Many2one('res.partner', string="c. Employer's name, address, and ZIP code",
                                         related='company_id.partner_id', readonly=True, store=True)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id', readonly=True, store=True)
    vat = fields.Char(related='company_id.vat', string='b. Employer identification number (EIN)', store=True)

    # W2 Info
    total_compensation = fields.Monetary('1. Wages, tips, and other compensation')
    federal_tax = fields.Monetary('2. Federal income tax withheld')
    ss_wage = fields.Monetary('3. Social security wages')
    ss_tax = fields.Monetary('4. Social security tax withheld')
    medicare_wage = fields.Monetary('5. Medicare wages and tips')
    medicare_tax = fields.Monetary('6. Medicare tax withheld')
    ss_tip = fields.Monetary('7. Social security tips')
    dependent_care = fields.Monetary('10. Dependent care benefits')

    line_ids = fields.One2many('wage.tax.report.line', 'wage_tax_report_id', string='Local Taxes')
    box12_ids = fields.One2many('wage.tax.report.box12', 'wage_tax_report_id', string='12. Information')

    REPORT_FIELDS_1 = ['ssnid', 'vat']
    REPORT_FIELDS_2 = ['total_compensation', 'federal_tax', 'ss_wage', 'ss_tax', 'medicare_wage', 'medicare_tax', 'dependent_care']
    REPORT_FIELDS_3 = ['is_statutory', 'is_retirement_plan', 'is_third_party_sick_pay']
    REPORT_FIELDS_4 = ['state_wage', 'state_tax', 'local_wage', 'local_tax']

    @api.depends('employee_id', 'year')
    def _compute_name(self):
        for record in self:
            record.name = "{} - {}".format(record.employee_id.name, record.year)

    def _execute_sql_report(self, query):
        self.env.cr.execute(query)
        return self.env.cr.dictfetchall()

    def _get_tax_info(self, company_id, employee_id):
        query = """
            SELECT name, tax_id, payroll_tax_id,
                SUM(actual_adjusted_gross) AS actual_adjusted_gross,
                SUM(tax_amt) AS tax_amt
            FROM payslip_tax
            WHERE tax_id IN {}
                AND DATE_PART('year', pay_date) = {}
                AND state in ('done')
                AND company_id = {}
                AND employee_id = {}
            GROUP BY name, tax_id, payroll_tax_id
        """.format(TAX_LIST, self.year, company_id, employee_id)

        return self._execute_sql_report(query)

    def _get_box12_ded_info(self, company_id, employee_id):
        query = """
            SELECT ROLL.w2_code,
                SUM(amount) AS amount,
                deduction_id
            FROM payslip_deduction SLIP
                JOIN payroll_deduction ROLL ON SLIP.deduction_id = ROLL.id
            WHERE ROLL.w2_code IS NOT NULL
                AND DATE_PART('year', pay_date) = {}
                AND state IN ('done')
                AND company_id = {}
                AND employee_id = {}
            GROUP BY w2_code, deduction_id
        """.format(self.year, company_id, employee_id)

        return self._execute_sql_report(query)

    def _get_box12_comp_info(self, company_id, employee_id):
        query = """
            SELECT ROLL.w2_code,
                SUM(amount) AS amount,
                compensation_id
            FROM payslip_compensation SLIP
                JOIN payroll_compensation ROLL ON SLIP.compensation_id = ROLL.id
            WHERE ROLL.w2_code IS NOT NULL
                AND DATE_PART('year', pay_date) = {}
                AND state IN ('done')
                AND company_id = {}
                AND employee_id = {}
            GROUP BY w2_code, compensation_id
        """.format(self.year, company_id, employee_id)

        return self._execute_sql_report(query)

    def update_report_info(self):
        """
        This main function is to get 941 data from Payslip.
        :return:
        """
        PayrollTax = self.env['payroll.tax']
        State = self.env['res.country.state']
        vertex = Vertex()
        # Box 10
        dependent_care_reg = self.env.ref('l10n_us_hr_payroll.payroll_deduction_14')
        dependent_care_sup = self.env.ref('l10n_us_hr_payroll.payroll_deduction_15')
        # Box 13
        retirement_plan_type = self.env.ref('l10n_us_hr_payroll.payroll_deduction_type_retirement')

        for record in self:
            company_id = record.company_id.id
            employee_id = record.employee_id.id
            domain = [('pay_date', '>=', date(int(record.year), 1, 1).strftime(DF)),
                      ('pay_date', '<=', date(int(record.year), 12, 31).strftime(DF)),
                      ('company_id', '=', company_id),
                      ('employee_id', '=', employee_id),
                      ('state', 'in', ['done'])]

            payslip_ids = self.env['payroll.payslip'].search(domain)
            payslip_deduction_ids = payslip_ids.mapped('deduction_ids')
            deduction_ids = payslip_deduction_ids.mapped('deduction_id')

            if not payslip_ids:
                continue

            is_retirement_plan = retirement_plan_type in deduction_ids.mapped('type_id')
            dependent_care = sum(payslip_deduction_ids.filtered(
                lambda x: x.deduction_id in [dependent_care_reg, dependent_care_sup]).mapped('amount'))

            # Box 1 of W2 must exclude all pre-tax contribution (Pre-tax deduction is link to Deduction Category)
            pre_deductions = payslip_deduction_ids.filtered('deduction_id.category_id')
            total_compensation = sum(payslip_ids.mapped('gross_pay')) - sum(pre_deductions.mapped('amount'))

            # Get Tax Data
            tax_data = record._get_tax_info(company_id, employee_id)

            federal_tax = 0
            ss_wage = ss_tax = 0
            medicare_wage = medicare_tax = 0
            line_data = {}

            for tax in tax_data:
                tax_id = tax.get('tax_id', False)
                tax_amt = tax.get('tax_amt', 0)
                actual_adjusted_gross = tax.get('actual_adjusted_gross', 0)

                if tax_id == FED_WH_ID:
                    federal_tax += tax_amt

                # Social Security
                elif tax_id == SOC_SEC_EE_ID:
                    ss_wage += actual_adjusted_gross
                    ss_tax += tax_amt

                # Medicare
                elif tax_id == MED_EE_ID:
                    medicare_wage += actual_adjusted_gross
                    medicare_tax += tax_amt

                # Local Tax
                elif tax_id in [STATE_WH_ID, COUNTY_WH_ID, CITY_WH_ID]:
                    payroll_tax_id = tax.get('payroll_tax_id', False)
                    if payroll_tax_id:
                        tax_obj = PayrollTax.browse(payroll_tax_id)
                        state_code, county_code = vertex._get_specific_geocode(tax_obj.geocode)
                        state_code = state_code.lstrip("0")
                        state_obj = State.search([('geocode', '=', state_code)], limit=1)

                        if state_code not in line_data:
                            line_data[state_code] = {
                                'state_name': '',
                                'state_wage': 0,
                                'state_tax': 0,
                                'local_wage': 0,
                                'local_tax': 0,
                                'local_name': '',
                            }

                        if tax_id == STATE_WH_ID:
                            line_data[state_code].update({
                                'state_name': state_obj.name,
                                'state_wage': actual_adjusted_gross,
                                'state_tax': tax_amt
                            })
                        elif tax_id == COUNTY_WH_ID:
                            line_data[state_code].update({
                                'local_wage': actual_adjusted_gross,
                                'local_tax': tax_amt,
                                'local_name': tax_obj.label
                            })
            line_ids = [(5, 0, 0)]
            line_ids.extend([(0, 0, line_data[key]) for key in line_data])

            # Box 12
            box12_data = record._get_box12_ded_info(company_id, employee_id)
            box12_data += record._get_box12_comp_info(company_id, employee_id)
            box12 = {}
            for tax in box12_data:
                w2_code = tax.get('w2_code', False)
                amount = tax.get('amount', 0)
                deduction_id = tax.get('deduction_id', False)
                compensation_id = tax.get('compensation_id', False)

                if w2_code not in box12:
                    box12[w2_code] = []

                box12[w2_code].extend([{
                    'compensation_id': compensation_id,
                    'deduction_id': deduction_id,
                    'amount': amount,
                    'w2_code': w2_code
                }])

            box12_ids = [(5, 0, 0)]
            for w2_code in box12:
                box12_ids.extend([(0, 0, {
                    'w2_code': w2_code,
                    'line_ids': [(0, 0, x) for x in box12[w2_code]]
                })])

            record.write({
                'partner_id': record.employee_id.address_home_id.id,
                'is_statutory': record.employee_id.is_statutory,
                'is_retirement_plan': is_retirement_plan,
                'is_third_party_sick_pay': record.employee_id.is_third_party_sick_pay,

                'total_compensation': total_compensation,
                'federal_tax': federal_tax,

                'ss_wage': ss_wage,
                'ss_tax': ss_tax,
                'ss_tip': 0,

                'medicare_wage': medicare_wage,
                'medicare_tax': medicare_tax,
                'dependent_care': dependent_care,

                'line_ids': line_ids,
                'box12_ids': box12_ids
            })

    def button_print_report(self):
        self.ensure_one()
        return self.env.ref('l10n_us_hr_payroll_reports.action_report_wage_tax_report').report_action(self)


class WageTaxReportBox12(models.Model):
    _name = 'wage.tax.report.box12'
    _description = 'Wage and Tax Statement Box 12'

    wage_tax_report_id = fields.Many2one('wage.tax.report', 'Wage Tax Report', ondelete='cascade')
    currency_id = fields.Many2one('res.currency', string='Currency', related='wage_tax_report_id.currency_id')

    w2_code = fields.Char('Code')
    amount = fields.Monetary('Amount', compute='_compute_amount', store=True)
    line_ids = fields.One2many('wage.tax.report.box12.line', 'box12_id', string='Lines')

    @api.depends('line_ids', 'line_ids.amount')
    def _compute_amount(self):
        for record in self:
            record.amount = sum(record.line_ids.mapped('amount'))


class WageTaxReportBox12Line(models.Model):
    _name = 'wage.tax.report.box12.line'
    _description = 'Wage and Tax Statement Box 12 Line'

    box12_id = fields.Many2one('wage.tax.report.box12', 'Box 12', ondelete='cascade')
    currency_id = fields.Many2one('res.currency', string='Currency', related='box12_id.currency_id')

    deduction_id = fields.Many2one('payroll.deduction', 'Deduction')
    compensation_id = fields.Many2one('payroll.compensation', 'Compensation')
    item = fields.Char('Item', compute='_compute_item', store=True)
    w2_code = fields.Char('Code')
    amount = fields.Monetary('Amount')

    @api.depends('deduction_id', 'compensation_id')
    def _compute_item(self):
        for record in self:
            record.item = record.deduction_id.name if record.deduction_id else record.compensation_id.name


class WageTaxReportLine(models.Model):
    _name = 'wage.tax.report.line'
    _description = 'Wage and Tax Statement Line'

    wage_tax_report_id = fields.Many2one('wage.tax.report', 'Wage Tax Report', ondelete='cascade')
    currency_id = fields.Many2one('res.currency', string='Currency', related='wage_tax_report_id.currency_id')

    state_name = fields.Char('15. State')
    state_wage = fields.Monetary('16. State wages, tips, etc.')
    state_tax = fields.Monetary('17. State income tax')
    local_wage = fields.Monetary('18. Local wages, tips, etc.')
    local_tax = fields.Monetary('19. Local income tax')
    local_name = fields.Char('20. Locality name')
