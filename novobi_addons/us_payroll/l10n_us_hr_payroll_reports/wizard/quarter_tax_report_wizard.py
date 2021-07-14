from odoo import api, fields, models, _
from odoo.exceptions import UserError


class QuarterTaxReportWizard(models.TransientModel):
    _name = 'quarter.tax.report.wizard'
    _description = 'Quarterly Tax Return Report (941) Wizard'

    quarter = fields.Selection([('1', 1), ('2', 2), ('3', 3), ('4', 4)], string='Quarter')
    year = fields.Char('Year', default=lambda self: fields.Datetime.now().year)

    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id', readonly=True, store=True)

    tax_due = fields.Monetary('Section 3121(q) Notice and Demand - Tax due on unreported tips (see instructions)')
    fractions_of_cents = fields.Monetary("Current quarter's adjustment for fractions of cents")
    sick_pay = fields.Monetary("Current quarter's adjustment for sick pay")
    group_term_insurance = fields.Monetary("Current quarter's adjustments for tips and group-term life insurance")
    tax_credit = fields.Monetary(
        "Qualified small business payroll tax credit for increasing research activities. Attach Form 8974")
    deposit = fields.Monetary('Total deposits for this quarter, including prior and current overpayments')

    def button_create_941(self):
        self.ensure_one()

        if not (self.year.isdigit() and len(self.year) == 4):
            raise UserError(_("Please enter a valid year."))

        report_id = self.env['quarter.tax.report'].sudo().create({
            'quarter': self.quarter,
            'year': self.year,
            'company_id': self.company_id.id,
            'tax_due': self.tax_due,
            'fractions_of_cents': self.fractions_of_cents,
            'sick_pay': self.sick_pay,
            'group_term_insurance': self.group_term_insurance,
            'tax_credit': self.tax_credit,
            'deposit': self.deposit
        })

        report_id.update_941_info()

        action = self.env.ref('l10n_us_hr_payroll_reports.action_quarter_tax_report').read()[0]
        action['views'] = [(self.env.ref('l10n_us_hr_payroll_reports.view_quarter_tax_report_form').id, 'form')]
        action['res_id'] = report_id.id

        return action
