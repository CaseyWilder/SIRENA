# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import api, models


class PayPeriod(models.Model):
    _inherit = 'pay.period'

    def button_print_check_paystub(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Print Checks & Paystubs',
            'view_mode': 'form',
            'res_model': 'print.check.paystub.wizard',
            'target': 'new',
            'context': {
                'default_pay_period_id': self.id,
                'default_type': 'check',
            }
        }

    def button_send_paystub(self):
        self.ensure_one()
        self.payslip_ids.action_send_paystub()
