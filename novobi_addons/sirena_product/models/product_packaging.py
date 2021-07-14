from odoo import fields, models


class ProductPackaging(models.Model):
    _inherit = 'product.packaging'

    name = fields.Char('Name', required=True)
    description = fields.Char('Description')

    length = fields.Float('Length', digits=(16, 2), copy=False, default=0)
    width = fields.Float('Width', digits=(16, 2), copy=False, default=0)
    height = fields.Float('Height', digits=(16, 2), copy=False, default=0)

    weight = fields.Float('Weight', digits=(16, 2), copy=False, default=0)

    product_tmpl_ids = fields.One2many('product.template', 'packaging_id', string='Products')
    product_product_ids = fields.One2many('product.product', 'packaging_id', string='Product Variants')

    def name_get(self):
        if not self:
            return []

        return [(record.id, record.name + ' ({} - {} - {})'.format(record.length, record.width, record.height)) for record in self]
