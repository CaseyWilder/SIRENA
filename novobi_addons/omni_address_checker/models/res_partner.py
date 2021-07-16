# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

import logging
from odoo import api, fields, models, tools, _

_logger = logging.getLogger(__name__)


class ResPartner(models.Model):
    _inherit = 'res.partner'

    is_address_validated = fields.Boolean(default=False)

    @api.model
    def update_validated_address(self, validated_address):
        self.write({
            'street': validated_address.StreetLines[0],
            'street2': validated_address.StreetLines[1] or '',
            'city': validated_address.City,
            'zip': validated_address.PostalCode,
            'state_id': next((state for state in self.env['res.country.state'].search([])
                              if state.code == validated_address.StateOrProvinceCode), None),
            'country_id': next((country for country in self.env['res.country'].search([])
                                if country.code == validated_address.CountryCode), None)
        })

    @api.depends('street', 'street2', 'city', 'state_id', 'country_id', 'zip')
    def if_change_address_reset_address_validation(self):
        self.is_address_validated = False
