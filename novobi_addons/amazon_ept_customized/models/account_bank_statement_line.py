from odoo import models, fields, api,_


class AccountBankStatementLine(models.Model):

    _inherit = "account.bank.statement.line"

    @api.model_create_multi
    def create(self, vals_list):
        """
        Inherit: move 'name' vals to 'payment_ref' (label) if statement is from Amazon
        """
        for vals in vals_list:
            if vals.get('statement_id', False):
                if self.env['account.bank.statement'].browse(vals['statement_id']).filtered('settlement_ref'):
                    if vals.get('name', False):
                        vals['payment_ref'] = vals.pop('name')
        return super().create(vals_list)

