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
        self.partner_id.street = validated_address.StreetLines[0]
        self.partner_id.street2 = validated_address.StreetLines[1] or ''
        self.partner_id.city = validated_address.City
        self.partner_id.zip = validated_address.PostalCode
        for state in self.env['res.country.state'].search([]):
            if state.code == validated_address.StateOrProvinceCode:
                self.partner_id.state_id = state
        for country in self.env['res.country'].search([]):
            if country.code == validated_address.CountryCode:
                self.partner_id.country_id = country
        self.is_address_validated = True
        self.partner_id.is_address_validated = True # Not sure if we need to set this or the above line will set it for us.
