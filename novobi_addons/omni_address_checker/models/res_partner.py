# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

import logging
from odoo import api, fields, models, tools, _

_logger = logging.getLogger(__name__)


class ResPartner(models.Model):
    _inherit = 'res.partner'

    is_address_validated = fields.Boolean(default=False)

    @api.depends('street', 'street2', 'city', 'state_id', 'country_id', 'zip')
    def if_change_address_reset_address_validation(self):
        self.is_address_validated = False
