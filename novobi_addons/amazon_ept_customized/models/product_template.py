from odoo import models, fields, api


class SaleOrderLine(models.Model):
    _inherit = 'product.template'

    dealer_cost = fields.Float("Dealer Cost", digits='Product Price')
