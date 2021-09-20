from odoo import api, models, fields, _


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def button_validate(self):
        """
        Save serial numbers of all move_line_ids and do "Check Availability" operation for all DOs with conflicting serial numbers.
        """
        if self.picking_type_code != 'outgoing':
            return super(StockPicking, self).button_validate()

        lot_ids = self.move_line_ids.mapped('lot_id')
        conflicting_lines = self.env['stock.move.line'].search([
            ('lot_id', 'in', lot_ids.ids),
            ('state', '=', 'assigned')
        ])
        delivery_orders = conflicting_lines.mapped('picking_id').filtered(lambda l: l.state == 'assigned') - self

        res = super(StockPicking, self).button_validate()

        if delivery_orders:
            delivery_orders.action_assign()

        return res
