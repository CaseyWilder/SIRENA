from odoo import api, fields, models, _


class PayslipTax(models.Model):
    _name = 'payslip.tax'
    _inherit = 'payslip.accumulated.amount'
    _description = 'Payslip Tax Withholding'
    _rec_name = 'payroll_tax_id'

    payroll_tax_id = fields.Many2one('payroll.tax', 'Payroll Tax', ondelete='restrict')
    name = fields.Char('Name')
    tax_id = fields.Char('Tax ID')
    geocode = fields.Char('GeoCode')
    school_dist = fields.Char('School District')
    payslip_id = fields.Many2one('payroll.payslip', 'Payslip', ondelete='restrict')
    employee_id = fields.Many2one('hr.employee', related='payslip_id.employee_id', store=True, readonly=True)
    company_id = fields.Many2one('res.company', related='payslip_id.company_id', readonly=True, store=True)
    currency_id = fields.Many2one('res.currency', related='employee_id.currency_id', store=True, readonly=True)
    is_er_tax = fields.Boolean(related='payroll_tax_id.is_er_tax', store=True, readonly=True)

    tax_amt = fields.Monetary('Tax Amount', help="""The dollar amount of the tax. This is what displays on the
            employee’s pay stub. Additionally, aggregations of this amount need to be fed back in with the next payroll
            as part of the AGGTAX group.""")

    adjusted_gross = fields.Monetary('Wage Base', help="""The adjusted gross used to calculate the tax. Aggregations
            of this field need to be fed back in with the next payroll as part of the AGGTAX group.""")
    actual_adjusted_gross = fields.Monetary('Actual Adjusted Gross', related='adjusted_gross', store=True)
    agg_adj_gross = fields.Monetary('Aggregated Adjusted Gross (YTD)')

    subject_gross_amt = fields.Monetary('Subject Gross Amount', help="""The subject gross amount, or the accumulated gross
            associated with Regular Pay that is subject to tax. Subject gross is reportable but might not have
            tax withheld for it. Subject Gross (from the Federal Withholding tax results) is what is aggregated
            and reported on the employee’s W2 form at the end of the year.""")
    taxable_gross_amt = fields.Monetary('Taxable Gross Amount', help="""The taxable gross amount, or the accumulated gross
            associated with Regular Pay that is taxable. Taxable gross is the amount of wages for
            which tax was calculated.""")
    base_amt_used = fields.Monetary('Base Amount Used', help="The wage base amount used in the calculation.")
    exempt_amt_used = fields.Monetary('Exempt Amount Used', help="The exemption amount used.")
    filing_status = fields.Integer('Filing Status')
    max_deduction_amt = fields.Monetary('Maximum Deduction Amount Used')
    rate_used = fields.Float('Rate Used', help="The tax rate that was used to calculate the tax.", digits=(16, 5))

    # For Additional Medicare
    med_add_tax_wages = fields.Monetary('Medicare Additional Tax Wages', default=0.0)
    med_add_tax_amt = fields.Monetary('Medicare Additional Tax Amount', default=0.0)

    # For Social Security Wage
    ss_tax_wages = fields.Monetary('Social Security Tax Wages')
    ss_tax_tips = fields.Monetary('Social Security Tax Tips')

    def _prepare_domain(self):
        domain = super(PayslipTax, self)._prepare_domain()
        payroll_tax_id = self.payroll_tax_id
        if payroll_tax_id:
            domain += [('payroll_tax_id', '=', payroll_tax_id.id)]
        return domain

    def calculate_accumulated_amount(self, amount):
        # Set `tax_amt` as amount field to get the data
        return super(PayslipTax, self).calculate_accumulated_amount(amount=amount)

    def write_accumulated_amount(self, vals):
        """
        Inherit from payslip.accumulated.amount to change the fields to Agg Adj Gross
        """
        if self.env.context.get('adj_gross', False):
            self.write({'agg_adj_gross': vals.get('ytd_amount', 0)})
        else:
            super().write_accumulated_amount(vals)

    @api.model
    def create(self, vals):
        res = super().create(vals)
        res.calculate_accumulated_amount(amount='tax_amt')
        res.with_context(adj_gross=True).calculate_accumulated_amount(amount='actual_adjusted_gross')
        return res
