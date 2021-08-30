from odoo import fields, models, api

SHIPPING_SERVICES = [
    ('HOME_DELIVERY_OR_GROUND', 'Home Delivery or Ground'),
    ('SMART_POST', 'Smart Post')
]


class ProductTemplate(models.Model):
    _inherit = "product.template"

    part_name_in_chinese = fields.Char(string="Part Name in Chinese")
    drawing_number = fields.Char(string="Drawing Number")
    substance = fields.Char(string="Substance")
    parts_spec_color = fields.Char(string="Parts Spec / Color")
    part_code = fields.Char(string="Part Code")

    delivery_carrier_id = fields.Selection(SHIPPING_SERVICES, string='Shipping Service')
    packaging_id = fields.Many2one('product.packaging', string='Custom Package', domain=[('is_custom', '=', True)])

    @api.model
    def _search(self, args, offset=0, limit=None, order=None, count=False, access_rights_uid=None):
        """
        Hide shared product list, e.g if current company is Paradise (hide_shared_products=True)
        """
        hide_companies = self.env['res.company'].sudo().search([('hide_shared_products', '=', True)])

        if not (set(self.env.companies.ids) - set(hide_companies.ids)):
            args = [('id', '=', -1)]

        return super()._search(args, offset, limit, order, count, access_rights_uid)


class ProductProduct(models.Model):
    _inherit = 'product.product'

    delivery_carrier_id = fields.Selection(related='product_tmpl_id.delivery_carrier_id', store=True, readonly=False)
    packaging_id = fields.Many2one(related='product_tmpl_id.packaging_id', store=True, readonly=False)
