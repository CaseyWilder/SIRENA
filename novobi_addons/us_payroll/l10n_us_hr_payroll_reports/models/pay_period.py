from odoo import models, fields, api


class PayPeriod(models.Model):
    _inherit = 'pay.period'

    def button_export_paycheck(self):
        """
        Button to redirect to paycheck report but only show paylips in this period.
        :return: action
        """
        self.ensure_one()
        action = self.env.ref('l10n_us_hr_payroll_reports.action_paycheck_report').read()[0]
        action['domain'] = [('pay_period_id', '=', self.id)]
        return action
