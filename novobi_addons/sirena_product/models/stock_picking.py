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
            return

        bom_ids = self.move_ids_without_package.mapped('bom_line_id').mapped('bom_id')
        if len(bom_ids) == 1:
            self.default_packaging_id = bom_ids.product_tmpl_id.packaging_id
            self.package_shipping_weight = bom_ids.product_tmpl_id.weight
