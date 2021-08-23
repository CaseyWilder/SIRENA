from odoo import models, fields, api
from odoo.exceptions import ValidationError


class ProductMapping(models.Model):

    _name = 'woo.product.mapping'
    _description = 'Woo Product SKU Mapping'

    odoo_product_id = fields.Many2one('product.product', string='Odoo Product')
    woo_product_id = fields.Many2one('woo.product.product.ept', string='Woo Product')
    woo_sku = fields.Char(string='Woo SKU', store=True, compute='_compute_woo_sku', inverse='_set_woo_sku')
    instance_id = fields.Many2one('woo.instance.ept', store=True, string='Instance')

    @api.constrains('woo_sku')
    def _check_woo_sku(self):
        product_mapping_obj = self.env['woo.product.mapping']
        for rec in self:
            if rec.woo_sku and product_mapping_obj.search_count([('woo_sku', '=', rec.woo_sku), ('instance_id', '=', rec.instance_id.id)]) > 1:
                raise ValidationError('Woo SKU must be unique per instance.')

    @api.depends('woo_product_id.default_code')
    def _compute_woo_sku(self):
        for rec in self:
            if rec.woo_product_id:
                rec.woo_sku = rec.woo_product_id.default_code

    def _set_woo_sku(self):
        woo_product_obj = self.env['woo.product.product.ept']
        for rec in self:
            if rec.woo_sku:
                rec.woo_product_id = woo_product_obj.search([('default_code', '=', rec.woo_sku), ('woo_instance_id', '=', rec.instance_id.id)], limit=1)
            else:
                rec.woo_product_id = False

    def write(self, vals):
        """
        Inherit: update linked product
        """
        res = super().write(vals)
        if vals.get('odoo_product_id', False) or vals.get('woo_sku', False):
            for rec in self:
                if rec.woo_product_id:
                    rec.woo_product_id.product_id = rec.odoo_product_id
                    rec.woo_product_id.woo_template_id.product_tmpl_id = rec.odoo_product_id.product_tmpl_id
        return res
