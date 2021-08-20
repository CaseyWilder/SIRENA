from odoo import models, fields, api


class ProductMapping(models.Model):

    _name = 'woo.product.mapping'
    _description = 'Woo Product SKU Mapping'

    odoo_product_id = fields.Many2one('product.product', string='Odoo Product')
    woo_product_id = fields.Many2one('woo.product.product.ept', string='Woo Product')
    woo_sku = fields.Char(string='Woo SKU', store=True, compute='_compute_woo_sku', inverse='_set_woo_sku')
    instance_id = fields.Many2one('woo.instance.ept', store=True, string='Instance')

    @api.depends('woo_product_id.default_code')
    def _compute_woo_sku(self):
        for rec in self:
            if rec.woo_product_id:
                rec.woo_sku = rec.woo_product_id.default_code

    def _set_woo_sku(self):
        for rec in self:
            if rec.woo_product_id:
                rec.woo_product_id.default_code = rec.woo_sku

    def write(self, vals):
        """
        Inherit: update linked product
        """
        res = super().write(vals)
        if vals.get('odoo_product_id', False):
            for rec in self:
                if rec.woo_product_id:
                    rec.woo_product_id.product_id = rec.odoo_product_id
                    rec.woo_product_id.woo_template_id.product_tmpl_id = rec.odoo_product_id.product_tmpl_id
        return res
