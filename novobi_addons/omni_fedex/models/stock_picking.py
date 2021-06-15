# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

import logging
from odoo import api, fields, models, tools, _

_logger = logging.getLogger(__name__)

class StockPicking(models.Model):
    _inherit = 'stock.picking'

    fedex_shipping_confirmation = fields.Selection(selection=[('SERVICE_DEFAULT', 'Service Default'),
                                                              ('NO_SIGNATURE_REQUIRED', 'No Signature Required'),
                                                              ('ADULT', 'Adult Signature Required'),
                                                              ('DIRECT', 'Direct Signature Required'),
                                                              ('INDIRECT', 'Indirect Signature Required')],
                                                   default='SERVICE_DEFAULT',
                                                   help='Confirmation')

    @api.model
    def _reset_label_fields(self):
        res = super(StockPicking, self)._reset_label_fields()
        res.update({
            'fedex_shipping_confirmation': False,
        })
        return res
