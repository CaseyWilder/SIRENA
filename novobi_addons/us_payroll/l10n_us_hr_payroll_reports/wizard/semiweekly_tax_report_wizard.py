from odoo import api, fields, models, _
from odoo.exceptions import UserError


class TaxLiabilitySemiweeklyWizard(models.TransientModel):
    _name = 'semiweekly.tax.report.wizard'
    _description = 'Tax Liability for Semiweekly Schedule Depositors Report Wizard'

    quarter = fields.Selection([('1', 1), ('2', 2), ('3', 3), ('4', 4)], string='Quarter')
    year = fields.Char('Year', default=lambda self: fields.Datetime.now().year)

    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)

    def button_create_report(self):
        self.ensure_one()
        if not (self.year.isdigit() and len(self.year) == 4):
            raise UserError(_("Please enter a valid year."))

        report_id = self.env['semiweekly.tax.report'].sudo().create({
            'quarter': self.quarter,
            'year': self.year,
            'company_id': self.company_id.id,
        })

        report_id.update_report_info()

        action = self.env.ref('l10n_us_hr_payroll_reports.action_semiweekly_tax_report').read()[0]
        action['views'] = [(self.env.ref('l10n_us_hr_payroll_reports.view_semiweekly_tax_report_form').id, 'form')]
        action['res_id'] = report_id.id

        return action
