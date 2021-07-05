from odoo import api, fields, models, _


class PayFrequency(models.Model):
    _inherit = 'pay.frequency'

    # ============== INIT DATA =========================
    @api.model
    def generate_demo_data(self):
        company = self.env.company
        pay_frequency = self.env.ref('l10n_us_hr_payroll_demo_data.weekly_frequency')
        pay_frequency.button_onboarding_confirm()

        overtime_rule = self.env.ref('l10n_us_hr_payroll_demo_data.delaware_rule')
        overtime_rule.button_onboarding_confirm()

        # Get all current employee
        employees = self.env['hr.employee'].search([('company_id', '=', company.id)])
        # Update pay frequency
        employees.with_context(from_partner='1').write({
            'pay_frequency_id': pay_frequency.id,
            'time_tracking_id': overtime_rule.id
        })
