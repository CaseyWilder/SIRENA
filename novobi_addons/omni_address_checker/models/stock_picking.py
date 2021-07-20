# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

import logging
from odoo import api, fields, models, tools, _

_logger = logging.getLogger(__name__)


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    is_address_validated = fields.Boolean(related='partner_id.is_address_validated')

    @api.model
    def update_address(self, validated_address):
        self.partner_id.update_validated_address(validated_address)
        self.partner_id.is_address_validated = True
