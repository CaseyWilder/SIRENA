from odoo import models, fields, api


class CommissionList(models.Model):
    _name = 'commission.list'
    _description = 'Commission List'

    product_id = fields.Many2one('product.product', string='Product')
    partner_id = fields.Many2one('res.partner', string='Contact')
    user_id = fields.Many2one('res.partner', string='Commission Salesperson')
    commission_amount = fields.Float(string='Commission Amount')
