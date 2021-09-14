from odoo import models, fields


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    commission_line_id = fields.Many2one('sale.order.line', string='Commission Line', copy=False)

    def action_open_commission_line(self):
        order_lines = self.mapped('commission_line_id')

        if not order_lines:
            return

        return {
            'name': 'Commission',
            'view_mode': 'tree,form',
            'res_model': 'sale.order.line',
            'domain': [('id', 'in', order_lines.ids)],
            'context': {
                'tree_view_ref': 'sirena_commission_report.view_sale_order_line_tree_commission',
            },
            'type': 'ir.actions.act_window',
            'target': 'current',
        }
