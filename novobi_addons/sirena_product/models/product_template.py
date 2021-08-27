from odoo import fields, models, api
from odoo.osv import expression


class ProductTemplate(models.Model):
    _inherit = "product.template"

    part_name_in_chinese = fields.Char(string="Part Name in Chinese")
    drawing_number = fields.Char(string="Drawing Number")
    substance = fields.Char(string="Substance")
    parts_spec_color = fields.Char(string="Parts Spec / Color")
    part_code = fields.Char(string="Part Code")

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

    packaging_id = fields.Many2one(related='product_tmpl_id.packaging_id', store=True, readonly=False)
