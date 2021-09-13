from odoo import models, fields, api


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    commission_user_id = fields.Many2one('res.partner', string='Commission Salesperson', store=True, compute='_compute_commission_amount')
    commission_amount = fields.Float(string='Commission Amount', store=True, compute='_compute_commission_amount')

    @api.depends('order_id.state')
    def _compute_commission_amount(self):
        CommissionList = self.env['commission.list']
        self.filtered(lambda x: x.order_id.state == 'cancel').write({
            'commission_user_id': False,
            'commission_amount': False
        })
        for rec in self.filtered(lambda x: x.order_id.state == 'sale'):
            commission = CommissionList.search([('product_id','=', rec.product_id.id), ('partner_id','=',rec.order_partner_id.id)], limit=1)
            if commission:
                rec.commission_user_id = commission.user_id
                rec.commission_amount = commission.commission_amount

