from odoo import api, fields, models, _


class ShippingAccount(models.Model):
    _inherit = 'shipping.account'

    capital_bearer = fields.Char(string='UPS Capital Insurance Bearer', groups="base.group_system")
    capital_client_id = fields.Char(string='UPS Capital Insurance Client ID', groups="base.group_system")
    capital_client_secret = fields.Char(string='UPS Capital Insurance Client Secret', groups="base.group_system")
    capital_partner_id = fields.Char(string='UPS Capital Insurance Partner ID', groups="base.group_system")
