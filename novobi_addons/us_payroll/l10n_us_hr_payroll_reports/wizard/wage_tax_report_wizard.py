from odoo import api, fields, models, _
from odoo.exceptions import UserError


class WageTaxReportWizard(models.TransientModel):
    _name = 'wage.tax.report.wizard'
    _description = 'Wage and Tax Statement (W-2) Wizard'

    year = fields.Char('Year', default=lambda self: fields.Datetime.now().year)
    employee_ids = fields.Many2many('hr.employee', string='Employees', domain="[('company_id', '=', company_id)]")

    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)

    def button_create_report(self):
        self.ensure_one()
        self = self.with_context(active_test=False)

        if not (self.year.isdigit() and len(self.year) == 4):
            raise UserError(_("Please enter a valid year."))

        report_ids = []
        for employee in self.employee_ids:
            report_id = self.env['wage.tax.report'].sudo().create({
                'year': self.year,
                'employee_id': employee.id,
                'company_id': self.company_id.id,
                'partner_id': employee.address_home_id.id,
                'company_partner_id': self.company_id.partner_id.id,
            })
            report_ids.append(report_id.id)
            report_id.update_report_info()

        action = self.env.ref('l10n_us_hr_payroll_reports.action_wage_tax_report').read()[0]
        action['domain'] = [('id', 'in', report_ids)]

        return action
