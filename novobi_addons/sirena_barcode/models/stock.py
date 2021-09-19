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
        delivery_orders = []
        for lot_id in lot_ids:
            conflicting_lines = self.env['stock.move.line'].search([('lot_id', '=', lot_id.id), ('state', '=', 'assigned')])
            for line in conflicting_lines:
                delivery_orders.append(self.env['stock.picking'].search([('id', '=', line.picking_id.id), ('id', '!=', self.id), ('state', '=', 'assigned')]))

        res = super(StockPicking, self).button_validate()

        if delivery_orders:
            delivery_orders = set(delivery_orders)
            for do in delivery_orders:
                do.action_assign()

        return res
