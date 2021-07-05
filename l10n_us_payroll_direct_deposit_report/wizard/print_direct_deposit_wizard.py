# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class PrintDirectDepositWizard(models.TransientModel):
    _name = 'print.direct.deposit.wizard'
    _description = 'Print Direct Deposit Wizard'

    pay_period_id = fields.Many2one('pay.period', 'Period', required=1)
    type = fields.Selection([('excel', 'Excel'), ('pdf', 'PDF')], string='Type', default='pdf', required=1)

    def button_print_direct_deposit(self):
        self.ensure_one()
        pay_period = self.pay_period_id
        if self.type == 'pdf':
            return pay_period.button_print_deposit_pdf()
        else:
            return pay_period.button_print_deposit_xls()
