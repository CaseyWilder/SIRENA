from odoo import models, fields, api


class SalesOrder(models.Model):
    _inherit = 'sale.order'

    delivery_status = fields.Selection(
        [('draft', 'Draft'), ('in_progress', 'In Progress'), ('done', 'Done'), ('cancel', 'Canceled')],
        string='Delivery Status', compute='_compute_delivery_status', store=True)

    @api.depends('picking_ids', 'picking_ids.state')
    def _compute_delivery_status(self):
        for record in self:
            state = 'draft'
            if record.picking_ids:
                delivery_states = record.picking_ids.mapped('state')
                if len(delivery_states) == 1 and delivery_states[0] in ['done', 'cancel']:
                    state = delivery_states[0]
                else:
                    state = 'in_progress'

            record.delivery_status = state
