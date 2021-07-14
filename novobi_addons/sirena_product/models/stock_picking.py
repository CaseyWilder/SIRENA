from odoo import models, fields, api


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    @api.onchange('delivery_carrier_id')
    def onchange_delivery_carrier_id(self):
        # TODO: multiple products in picking
        super().onchange_delivery_carrier_id()

        product_ids = self.move_line_ids.mapped('product_id')
        if len(product_ids) == 1:
            self.default_packaging_id = product_ids.packaging_id
