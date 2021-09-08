from odoo import api, models, fields, _


class StockPickingPackage(models.Model):
    _inherit = 'stock.picking.package'

    packaging_id = fields.Many2one(domain=[('is_custom', '=', True)])
