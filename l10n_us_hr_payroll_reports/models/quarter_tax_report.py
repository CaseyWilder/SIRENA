from odoo import api, fields, models
from odoo.tools import float_compare
from datetime import date
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT as DF
from odoo.addons.l10n_us_hr_payroll.utils.vertex import FED_WH_ID, SOC_SEC_EE_ID, SOC_SEC_ER_ID, MED_EE_ID, MED_ER_ID

TAX_941 = (FED_WH_ID, SOC_SEC_EE_ID, SOC_SEC_ER_ID, MED_EE_ID, MED_ER_ID)
ADD_MEDICARE_RATE = 0.009


class QuarterTaxReport(models.Model):
    _name = 'quarter.tax.report'
    _description = 'Quarterly Tax Return Report (941)'

    # List of fields to show in report
    REPORT_FIELDS_1 = ['total_compensation', 'federal_tax']
    REPORT_FIELDS_2 = [
        ['5a. Taxable Social Security wages', 'tax_ss_wages_1', 'ss_rate', 'tax_ss_wages_2'],
        ['Actual Social Security Tax withheld', 'actual_tax_ss_wages', '', ''],
        ['5c. Taxable Medicare wages & tips', 'tax_medicare_1', 'medicare_rate', 'tax_medicare_2'],
        ['Actual Medicare Tax withheld', 'actual_tax_medicare', '', ''],
        ['5d. Taxable wages & tips subject to Additional Medicare Tax withholding', 'tax_add_medicare_1', 'add_medicare_rate', 'tax_add_medicare_2'],
        ['Actual Additional Medicare Tax withheld', 'actual_tax_add_medicare', '', ''],
    ]
    REPORT_FIELDS_3 = ['tax_due', 'total_tax_before', 'fractions_of_cents', 'sick_pay',
                       'group_term_insurance', 'total_tax_after', 'tax_credit', 'total_tax_final',
                       'deposit', 'balance_due', 'overpayment']
    REPORT_FIELD_4 = ['month_1', 'month_2', 'month_3']

    name = fields.Char('Name', compute='_compute_name', store=True)
    quarter = fields.Selection([('1', 'First'), ('2', 'Second'), ('3', 'Third'), ('4', 'Fourth')], string='Quarter')
    year = fields.Char('Year')

    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id', readonly=True, store=True)

    vat = fields.Char(related='company_id.vat')

    # Line 1-5
    no_employees = fields.Integer('1. Number of Employees')
    total_compensation = fields.Monetary('2. Wages, tips, and other compensation')
    federal_tax = fields.Monetary('3. Federal income tax withheld from wages, tips, and other compensation')
    tax_exempt = fields.Boolean(
        '4. If no wages, tips, and other compensation are subject to social security or Medicare tax')
    ss_rate = fields.Float('Social Security Rate', digits=(16, 3))
    medicare_rate = fields.Float('Medicare Rate', digits=(16, 3))
    add_medicare_rate = fields.Float('Additional Medicare Rate', digits=(16, 3))
    tax_ss_wages_1 = fields.Monetary('5a. Taxable Social Security wages - Col 1')
    tax_ss_wages_2 = fields.Monetary('5a. Taxable Social Security wages - Col 2')
    actual_tax_ss_wages = fields.Monetary('Actual Social Security Tax withheld')

    tax_ss_tips_1 = fields.Monetary('5b. Taxable Social Security tips - Col 1')
    tax_ss_tips_2 = fields.Monetary('5b. Taxable Social Security tips - Col 2')
    tax_medicare_1 = fields.Monetary('5c. Taxable Medicare wages & tips - Col 1')
    tax_medicare_2 = fields.Monetary('5c. Taxable Medicare wages & tips - Col 2')
    actual_tax_medicare = fields.Monetary('Actual Medicare Tax withheld')

    tax_add_medicare_1 = fields.Monetary(
        '5d. Taxable wages & tips subject to Additional Medicare Tax withholding - Col 1')
    tax_add_medicare_2 = fields.Monetary(
        '5d. Taxable wages & tips subject to Additional Medicare Tax withholding - Col 2')
    actual_tax_add_medicare = fields.Monetary('Actual Additional Medicare Tax withheld')
    total_5e = fields.Monetary('5e. Add Column 2 from lines 5a, 5c, and 5d', compute='_compute_total_5e',
                               store=True)
    tax_due = fields.Monetary('5f. Section 3121(q) Notice and Demand - Tax due on unreported tips (see instructions)')

    # Line 6-10
    total_tax_before = fields.Monetary('6. Total taxes before adjustments. Add lines 3, 5e, and 5f',
                                       compute='_compute_total_tax_before', store=True)
    fractions_of_cents = fields.Monetary("7. Current quarter's adjustment for fractions of cents")
    sick_pay = fields.Monetary("8. Current quarter's adjustment for sick pay")
    group_term_insurance = fields.Monetary("9. Current quarter's adjustments for tips and group-term life insurance")
    total_tax_after = fields.Monetary('10. Total taxes after adjustments. Combine lines 6 through 9',
                                      compute='_compute_total_tax_after', store=True)

    # Line 11-15
    tax_credit = fields.Monetary(
        "11. Qualified small business payroll tax credit for increasing research activities. Attach Form 8974")
    total_tax_final = fields.Monetary('12. Total taxes after adjustments and credits. Subtract line 11 from line 10',
                                      compute='_compute_total_tax_final', store=True)
    deposit = fields.Monetary('13. Total deposits for this quarter, including prior and current overpayments')
    balance_due = fields.Monetary(
        '14. Balance due. If line 12 is more than 13, enter the difference and see instructions',
        compute='_compute_balance_due', store=True)
    overpayment = fields.Monetary('15. Overpayment. If line 13 is more than line 12, enter the difference',
                                  compute='_compute_balance_due', store=True)

    # PART 2
    month_1 = fields.Monetary('Tax Liability Month 1')
    month_2 = fields.Monetary('Tax Liability Month 2')
    month_3 = fields.Monetary('Tax Liability Month 3')
    total_tax_liability = fields.Monetary('Total Tax Liability', compute='_compute_total_tax_liability', store=True)

    @api.depends('quarter', 'year')
    def _compute_name(self):
        for record in self:
            record.name = "{} Quarter, {}".format(dict(record._fields['quarter'].selection).get(record.quarter),
                                                  record.year)

    @api.depends('tax_ss_wages_2', 'tax_ss_tips_2', 'tax_medicare_2', 'tax_add_medicare_2')
    def _compute_total_5e(self):
        for record in self:
            record.total_5e = record.tax_ss_wages_2 + record.tax_ss_tips_2 + record.tax_medicare_2 + record.tax_add_medicare_2

    @api.depends('federal_tax', 'total_5e', 'tax_due')
    def _compute_total_tax_before(self):
        for record in self:
            record.total_tax_before = record.federal_tax + record.total_5e + record.tax_due

    @api.depends('total_tax_before', 'fractions_of_cents', 'sick_pay', 'group_term_insurance')
    def _compute_total_tax_after(self):
        for record in self:
            record.total_tax_after = record.total_tax_before + record.fractions_of_cents + record.sick_pay + record.group_term_insurance

    @api.depends('total_tax_after', 'tax_credit')
    def _compute_total_tax_final(self):
        for record in self:
            record.total_tax_final = record.total_tax_after - record.tax_credit

    @api.depends('total_tax_final', 'deposit')
    def _compute_balance_due(self):
        for record in self:
            if float_compare(record.total_tax_final, record.deposit, precision_digits=2) == 1:
                record.balance_due = record.total_tax_final - record.deposit
                record.overpayment = 0
            elif float_compare(record.total_tax_final, record.deposit, precision_digits=2) == -1:
                record.balance_due = 0
                record.overpayment = record.total_tax_final - record.deposit
            else:
                record.balance_due = record.overpayment = 0

    @api.depends('month_1', 'month_2', 'month_3')
    def _compute_total_tax_liability(self):
        for record in self:
            record.total_tax_liability = record.month_1 + record.month_2 + record.month_3

    def _get_tax_info(self, company_id):
        query = """
            SELECT name, tax_id, rate_used,
                SUM(actual_adjusted_gross) AS actual_adjusted_gross,
                SUM(tax_amt) AS tax_amt,
                SUM(med_add_tax_wages) AS med_add_tax_wages,
                SUM(med_add_tax_amt) AS med_add_tax_amt,
                DATE_PART('month', pay_date) AS pay_month
            FROM payslip_tax
            WHERE tax_id IN {}
                AND DATE_PART('year', pay_date) = {}
                AND DATE_PART('quarter', pay_date) = {}
                AND state IN ('done')
                AND company_id = {}
            GROUP BY name, tax_id, pay_month, rate_used
            ORDER BY pay_month;
        """.format(TAX_941, self.year, int(self.quarter), company_id)
        self.env.cr.execute(query)
        return self.env.cr.dictfetchall()

    def update_941_info(self):
        """
        This main function is to get 941 data from Payslip.
        :return:
        """
        for record in self:
            company_id = self.company_id.id
            domain = [
                ('pay_date', '>=', date(int(record.year), 1, 1).strftime(DF)),
                ('pay_date', '<=', date(int(record.year), 12, 31).strftime(DF)),
                ('quarter', '=', record.quarter),
                ('company_id', '=', company_id),
                ('state', 'in', ['done'])
            ]
            pay_period_ids = self.env['pay.period'].search(domain)
            payslip_ids = pay_period_ids.mapped('payslip_ids')

            if not payslip_ids:
                return

            tax_data = self._get_tax_info(company_id)

            # Line 1-5
            employee_ids = payslip_ids.mapped('employee_id')
            total_compensation = sum(pay_period_ids.mapped('total_gross_pay'))

            # Initial
            federal_tax = ss_rate = medicare_rate = 0
            actual_tax_ss_wages = actual_tax_medicare = actual_tax_add_medicare = 0
            total_ss_tax = tax_ss_wages_1 = tax_medicare_1 = tax_medicare_2 = tax_add_medicare_1 = tax_add_medicare_2 = 0
            month_1 = month_2 = month_3 = 0

            for tax in tax_data:
                tax_id = tax.get('tax_id', False)
                tax_amt = tax.get('tax_amt', 0)
                actual_adjusted_gross = tax.get('actual_adjusted_gross', 0)
                pay_month = tax.get('pay_month', 0)

                # Tax Liability per month
                if pay_month % 3 == 1:
                    month_1 += tax_amt
                elif pay_month % 3 == 2:
                    month_2 += tax_amt
                else:
                    month_3 += tax_amt

                if tax_id == FED_WH_ID:
                    federal_tax += tax_amt

                # Social Security
                elif tax_id == SOC_SEC_EE_ID:
                    tax_ss_wages_1 += actual_adjusted_gross
                    ss_rate = tax.get('rate_used', 0) * 2   # Multiple by 2 since we also include ER side
                    actual_tax_ss_wages += tax_amt * 2

                # Medicare. TODO: Medicare might be different because of 125 Supp?
                elif tax_id == MED_ER_ID:
                    tax_medicare_1 += actual_adjusted_gross
                    medicare_rate = tax.get('rate_used', 0) * 2     # Multiple by 2 since we also include ER side
                    actual_tax_medicare += tax_amt * 2

                # Only employees pay for Additional medicare
                elif tax_id == MED_EE_ID:
                    tax_add_medicare_1 += tax.get('med_add_tax_wages', 0)
                    tax_add_medicare_2 += tax.get('med_add_tax_amt', 0)
                    actual_tax_add_medicare += tax.get('med_add_tax_amt', 0)

            add_medicare_rate = ADD_MEDICARE_RATE
            if tax_add_medicare_1 and tax_add_medicare_2:
                add_medicare_rate = tax_add_medicare_2 / tax_add_medicare_1

            tax_ss_wages_2 = tax_ss_wages_1 * ss_rate
            tax_medicare_2 = tax_medicare_1 * medicare_rate
            tax_add_medicare_2 = tax_add_medicare_1 * add_medicare_rate

            record.write({
                'no_employees': len(employee_ids),
                'total_compensation': total_compensation,
                'federal_tax': federal_tax,

                'tax_ss_wages_1': tax_ss_wages_1,
                'tax_ss_wages_2': tax_ss_wages_2,
                'actual_tax_ss_wages': actual_tax_ss_wages,
                'tax_ss_tips_1': 0,
                'tax_ss_tips_2': 0,

                'tax_medicare_1': tax_medicare_1,
                'tax_medicare_2': tax_medicare_2,
                'actual_tax_medicare': actual_tax_medicare,
                'tax_add_medicare_1': tax_add_medicare_1,
                'tax_add_medicare_2': tax_add_medicare_2,
                'actual_tax_add_medicare': actual_tax_add_medicare,

                'ss_rate': ss_rate,
                'medicare_rate': medicare_rate,
                'add_medicare_rate': add_medicare_rate,

                'month_1': month_1,
                'month_2': month_2,
                'month_3': month_3,
            })

    def button_print_report(self):
        return self.env.ref('l10n_us_hr_payroll_reports.action_report_quarter_tax_report').report_action(self)
