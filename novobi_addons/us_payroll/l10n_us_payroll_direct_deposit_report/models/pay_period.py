# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models
from odoo.exceptions import Warning


class PayPeriod(models.Model):
    _inherit = 'pay.period'

    def button_print_deposit(self):
        self.ensure_one()
        if not any(payslip.payment_method == 'deposit' for payslip in self.payslip_ids):
            raise Warning('There is no employee using direct deposit!')
        action = self.env.ref('l10n_us_payroll_direct_deposit_report.action_print_direct_deposit_wizard').read()[0]
        return action

    def button_print_deposit_pdf(self):
        return self.env.ref('l10n_us_payroll_direct_deposit_report.action_report_direct_deposit_payroll').report_action(self)

    def button_print_deposit_xls(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': '/payroll_direct_deposit/{}'.format(self.id),
            'target': 'current',
        }
