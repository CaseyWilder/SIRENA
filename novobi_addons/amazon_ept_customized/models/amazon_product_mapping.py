from odoo import models, fields, api


class ProductMapping(models.Model):

    _name = 'amazon.product.mapping'
    _description = 'Amazon Product SKU Mapping'

    odoo_product_id = fields.Many2one('product.product', string='Odoo Product')
    amazon_product_id = fields.Many2one('amazon.product.ept', string='Amazon Product')
    amz_sku = fields.Char(string='Amazon SKU', store=True, compute='_compute_amz_sku', inverse='_set_amz_sku')
    instance_id = fields.Many2one("amazon.instance.ept", store=True, string="Instance")

    @api.depends('amazon_product_id.seller_sku')
    def _compute_amz_sku(self):
        for rec in self:
            if rec.amazon_product_id:
                rec.amz_sku = rec.amazon_product_id.seller_sku

    def _set_amz_sku(self):
        for rec in self:
            if rec.amazon_product_id:
                rec.amazon_product_id.seller_sku = rec.amz_sku

    def write(self, vals):
        """
        Inherit: update linked product
        """
        res = super().write(vals)
        if vals.get('odoo_product_id', False):
            for rec in self:
                if rec.amazon_product_id:
                    rec.amazon_product_id.product_id = rec.odoo_product_id
        return res
