from odoo import models, fields, api


class SaleOrderLine(models.Model):
    _inherit = 'stock.picking'

    @api.depends('shipping_cost')
    def update_order_line_shipping_cost(self):
        products = self.env['amazon.product.ept'].search([]).mapped('product_id')
        for rec in self:
            if rec.sale_id:
                rec.sale_id.order_line.filtered(lambda x: x.product_id in products).write(
                    {'shipping_cost': rec.shipping_cost})
