from odoo import models, api


class Employee(models.Model):
    _inherit = 'hr.employee'

    @api.onchange('payment_method')
    def _onchange_payment_method(self):
        """
        Keep all payment accounts if changing payment method.
        """
        # self.payment_account_ids = [(5,)]
        pass
