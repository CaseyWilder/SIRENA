from odoo import models, fields, api
from odoo.exceptions import ValidationError


class ProductMapping(models.Model):

    _name = 'amazon.product.mapping'
    _description = 'Amazon Product SKU Mapping'

    odoo_product_id = fields.Many2one('product.product', string='Odoo Product')
    amazon_product_id = fields.Many2one('amazon.product.ept', string='Amazon Product')
    amz_sku = fields.Char(string='Amazon SKU', store=True, compute='_compute_amz_sku', inverse='_set_amz_sku')
    instance_id = fields.Many2one("amazon.instance.ept", store=True, string="Instance")

    @api.constrains('amz_sku')
    def _check_amz_sku(self):
        product_mapping_obj = self.env['amazon.product.mapping']
        for rec in self:
            if rec.amz_sku and product_mapping_obj.search_count([('amz_sku', '=', rec.amz_sku), ('instance_id', '=', rec.instance_id.id)]) > 1:
                raise ValidationError('Amazon SKU must be unique per instance.')

    @api.depends('amazon_product_id.seller_sku')
    def _compute_amz_sku(self):
        for rec in self:
            if rec.amazon_product_id:
                rec.amz_sku = rec.amazon_product_id.seller_sku

    def _set_amz_sku(self):
        amazon_product_obj = self.env['amazon.product.ept']
        for rec in self:
            if rec.amz_sku:
                rec.amazon_product_id = amazon_product_obj.search([('seller_sku', '=', rec.amz_sku), ('instance_id', '=', rec.instance_id.id)], limit=1)
            else:
                rec.amazon_product_id = False

    def write(self, vals):
        """
        Inherit: update linked product
        """
        res = super().write(vals)
        if vals.get('odoo_product_id', False) or vals.get('amz_sku', False):
            for rec in self:
                if rec.amazon_product_id:
                    rec.amazon_product_id.product_id = rec.odoo_product_id
        return res
