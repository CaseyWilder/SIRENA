# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

import logging
from odoo import api, fields, models, tools, _

_logger = logging.getLogger(__name__)

class StockPicking(models.Model):
    _inherit = 'stock.picking'

    ups_service_type = fields.Selection(related='delivery_carrier_id.ups_default_service_type')

    ups_shipping_confirmation = fields.Selection(selection=[('2', 'Signature Required'),
                                                            ('3', 'Adult Signature Required')],
                                                 help='Confirmation')

    @api.model
    def _reset_label_fields(self):
        res = super(StockPicking, self)._reset_label_fields()
        res.update({
            'ups_shipping_confirmation': False,
        })
        return res
