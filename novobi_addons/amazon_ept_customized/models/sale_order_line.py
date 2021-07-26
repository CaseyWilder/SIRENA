from odoo import models, fields, api


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    is_amazon_order_item = fields.Boolean("Is an Amazon order item", compute='_compute_is_amazon_order_item', store=True)
    date_order = fields.Datetime("Order Date", related='order_id.date_order', store=True)
    retail_price = fields.Monetary("Retail Price", compute='_compute_gross_pay', store=True)
    amazon_fee = fields.Monetary("Amazon Fee", compute='_compute_gross_pay', store=True)
    gross_pay = fields.Monetary("Gross Pay", compute='_compute_gross_pay', store=True)
    shipping_cost = fields.Monetary("Shipping Cost",compute='_compute_shipping_cost', store=True)
    gross_profit = fields.Monetary("Gross profit", compute='_compute_net_profit', store=True)
    dealer_cost = fields.Float("Dealer Cost", related='product_id.dealer_cost', store=True)
    net_profit = fields.Monetary("Net Profit", compute='_compute_net_profit', store=True)
    is_florida_tax = fields.Boolean("Is Florida tax?", compute='_compute_is_florida_tax', store=True)

    @api.depends('product_id')
    def _compute_is_amazon_order_item(self):
        products = self.env['amazon.product.ept'].search([('product_id', 'in', self.mapped('product_id').ids)]).mapped('product_id')
        for rec in self:
            rec.is_amazon_order_item = bool(rec.order_id.amz_instance_id and rec.rec.product_id in products)

    @api.depends('order_partner_id')
    def _compute_is_florida_tax(self):
        for rec in self:
            rec.is_florida_tax = bool(rec.order_id.partner_shipping_id.state_id.code == 'FL')

    @api.depends('order_id.state','price_subtotal')
    def _compute_gross_pay(self):
        sale_order_line_obj = self.env['sale.order.line']
        for rec in self.filtered(lambda x: x.is_amazon_order_item and x.order_id.state == 'sale'):
            related_lines = sale_order_line_obj.search([('is_amazon_order_item', '=', False), ('amazon_order_item_id', 'ilike', rec.amazon_order_item_id)])
            rec.retail_price = rec.price_subtotal + related_lines.filtered(lambda x: x.product_id.id == x.order_id.amz_seller_id.promotion_discount_product_id.id).price_subtotal
            rec.amazon_fee = 0.15*(rec.price_subtotal + sum(related_lines.mapped('price_subtotal')))
            if rec.order_id.amz_instance_id.market_place_id == 'A2EUQ1WTGCTBG2':
                rec.amazon_fee += 0.029*rec.line_tax_amount
            rec.gross_pay = rec.retail_price - rec.amazon_fee

    @api.depends('gross_pay','shipping_cost','dealer_cost')
    def _compute_net_profit(self):
        for rec in self.filtered('is_amazon_order_item'):
            rec.gross_profit = rec.gross_pay - rec.shipping_cost
            rec.net_profit = rec.gross_profit - rec.product_id.dealer_cost

    @api.depends('order_id.picking_ids.shipping_cost')
    def _compute_shipping_cost(self):
        for rec in self:
            order = rec.order_id
            amz_order_lines = order.order_line.filtered('is_amazon_order_item')
            if amz_order_lines:
                shipping_cost = sum(order.picking_ids.filtered(
                    lambda x: x.picking_type_code == 'outgoing' and x.state != 'cancel').mapped('shipping_cost'))
                rec.shipping_cost = shipping_cost/len(amz_order_lines)



