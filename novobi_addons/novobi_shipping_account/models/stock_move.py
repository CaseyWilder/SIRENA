# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
import logging

_logger = logging.getLogger(__name__)

class StockMove(models.Model):
    _inherit = 'stock.move'

    remaining_backorder_qty = fields.Float('Remaining Backorder Qty', compute='_compute_remaining_backorder_qty',
                                           digits='Product Unit of Measure')

    def _compute_remaining_backorder_qty(self):
        for record in self:
            moves = record.sale_line_id.move_ids.filtered(lambda r: (r.id <= record.id and r.state != 'cancel'))
            record.remaining_backorder_qty = max(record.sale_line_id.product_uom_qty - sum(moves.mapped('product_uom_qty')), 0.0)