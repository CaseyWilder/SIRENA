# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class PrintCheckPaystubWizard(models.TransientModel):
    _name = 'print.check.paystub.wizard'
    _description = 'Print Check & Paystub Wizard'

    will_print_check = fields.Boolean('Print Checks', default=False)
    will_print_paystub = fields.Boolean('Print Paystubs', default=True)

    pay_period_id = fields.Many2one('pay.period', 'Period', required=1)
    payslip_ids = fields.Many2many('payroll.payslip')

    @api.onchange('pay_period_id', 'will_print_check')
    def _onchange_will_print_check(self):
        payslip_domain = [('pay_period_id', '=', self.pay_period_id.id)]
        if self.will_print_check:
            payslip_domain.append(('payment_method', '=', 'check'))
        return {
            'domain': {'payslip_ids': payslip_domain}
        }

    def button_print(self):
        self.ensure_one()
        return self.payslip_ids\
            .with_context(check=self.will_print_check, paystub=self.will_print_paystub)\
            .print_check_paystub()
