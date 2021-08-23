# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from odoo import models, fields, _
from odoo.exceptions import UserError


class UpdateDoneQuantities(models.TransientModel):
    _name = 'update.done.quantities'
    _description = 'Transfer: Update Done Quantities'

    pick_id = fields.Many2one('stock.picking', 'Transfer')

    def process(self):
        picking = self.pick_id
        # If still in draft => confirm and assign
        if picking.state == 'draft':
            picking.action_confirm()
            if picking.state != 'assigned':
                picking.action_assign()
                if picking.state != 'assigned':
                    raise UserError(_("Could not reserve all requested products. Please use the \'Mark as Todo\' button to handle the reservation manually."))
        for move in picking.move_lines.filtered(lambda m: m.state not in ['done', 'cancel']):
            move_lines = move._get_move_lines()
            if not move_lines:
                # do not impact reservation here
                move_line = self.env['stock.move.line'].create(
                    dict(move._prepare_move_line_vals(), qty_done=move.product_uom_qty))
                move.write({'move_line_ids': [(4, move_line.id)]})
            else:
                for move_line in move.move_line_ids:
                    move_line.qty_done = move_line.product_uom_qty
        if self.env.context.get('update_done_callback') == 'confirm_create_shipping_label':
            return picking.button_validate()
        return picking.open_create_label_form()
