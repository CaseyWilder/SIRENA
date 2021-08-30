from odoo import models, fields, api


class AccountTax(models.Model):
    _inherit = 'account.tax'

    @api.model
    def _create_amazon_python_tax(self):
        """
        Override: Add company when creating Amazon Tax, price_include = False
        """
        company_id = self.env.ref('sirena_base.sirena_inc_ottawa').id,
        amz_tax_id = self.search(
            [('company_id', '=', company_id),
             ('python_compute', '=', 'result = (price_unit * quantity * line_tax_amount_percent) / 100')])
        if not amz_tax_id:
            tax_vals = {
                'name': 'Canada Amazon Tax',
                'amount_type': 'code',
                'type_tax_use': 'sale',
                'amount': 0.00,
                'price_include': False,
                'python_compute': 'result = (price_unit * quantity * line_tax_amount_percent) / 100',
                'company_id': company_id
            }
            self.create(tax_vals)
        return True
