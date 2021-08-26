# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

import logging

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

class PickingPackage(models.Model):
    _name = 'stock.picking.package'
    _description = 'Package for Picking'
    _order = 'picking_id, id'

    picking_id = fields.Many2one('stock.picking', 'Picking', required=True, index=True, ondelete='cascade')
    provider = fields.Char(string='Provider', related='picking_id.provider', readonly=True)
    packaging_id = fields.Many2one('product.packaging',
                                   string='Package Type',
                                   copy=False)
    weight = fields.Float(help='Package Shipping Weight (in pounds)')

    weight_oz = fields.Float(help='Package Shipping Weight (in ounces)')

    length = fields.Float('Length', help='Package Length (in inches)', digits=(16, 2), copy=False)
    width = fields.Float('Width', help='Package Width (in inches)', digits=(16, 2), copy=False)
    height = fields.Float('Height', help='Package Height (in inches)', digits=(16, 2), copy=False)
    carrier_tracking_ref = fields.Char(string='Tracking Reference', copy=False)
    handling_fee = fields.Monetary(string='Handling Charges', help='Handling Charges for each package')
    currency_id = fields.Many2one('res.currency', string='Currency', related='picking_id.currency_id')

    @api.onchange('packaging_id')
    def _onchange_packaging_id(self):
        if self.packaging_id:
            self.update({
                'length': self.packaging_id.length,
                'width': self.packaging_id.width,
                'height': self.packaging_id.height
            })

    @api.constrains('weight')
    def _check_weight(self):
        if any(r.weight <= 0 and r.weight_oz <=0 for r in self):
            raise ValidationError(_('Weight for Shipping Package must be greater than 0.'))
