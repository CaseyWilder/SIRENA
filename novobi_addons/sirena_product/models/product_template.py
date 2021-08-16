from odoo import fields, models, api


class ProductTemplate(models.Model):
    _inherit = "product.template"

    part_name_in_chinese = fields.Char(string="Part Name in Chinese")
    drawing_number = fields.Char(string="Drawing Number")
    substance = fields.Char(string="Substance")
    parts_spec_color = fields.Char(string="Parts Spec / Color")
    part_code = fields.Char(string="Part Code")

    packaging_id = fields.Many2one('product.packaging', string='Custom Package')


class ProductProduct(models.Model):
    _inherit = 'product.product'

    packaging_id = fields.Many2one(related='product_tmpl_id.packaging_id', store=True, readonly=False)
