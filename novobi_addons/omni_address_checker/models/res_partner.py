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
        country = self.env['res.country'].search([('code', '=', validated_address.CountryCode)])
        for state_idx in self.env['res.country.state'].search([]):
            if state_idx.code == validated_address.StateOrProvinceCode and state_idx.country_id == country:
                state = state_idx
        self.write({
            'street': validated_address.StreetLines[0],
            'street2': validated_address.StreetLines[1] or '',
            'city': validated_address.City,
            'zip': validated_address.PostalCode,
            'state_id': state,
            'country_id': country
        })

    @api.depends('street', 'street2', 'city', 'state_id', 'country_id', 'zip')
    def if_change_address_reset_address_validation(self):
        self.is_address_validated = False
