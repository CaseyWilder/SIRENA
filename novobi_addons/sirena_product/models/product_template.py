from odoo import fields, models, api


class ProductTemplate(models.Model):
    _inherit = "product.template"

    part_name_in_chinese = fields.Char(string="Part Name in Chinese")
    drawing_number = fields.Char(string="Drawing Number")
    substance = fields.Char(string="Substance")
    parts_spec_color = fields.Char(string="Parts Spec / Color")
    part_code = fields.Char(string="Part Code")
