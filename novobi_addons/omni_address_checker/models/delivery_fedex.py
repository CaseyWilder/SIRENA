# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from odoo.tools import pdf, DEFAULT_SERVER_DATE_FORMAT
from odoo import api, models, fields, _, tools
from odoo.addons.delivery_fedex.models.delivery_fedex import _convert_curr_iso_fdx

from .fedex_request import FedexRequest
from decimal import Decimal

import datetime
import logging

_logger = logging.getLogger(__name__)


class ProviderFedex(models.Model):
    _inherit = 'delivery.carrier'

    @api.model
    def fedex_validate_address(self, picking):
        shipping_account = self.shipping_account_id
        delivery_address = picking.partner_id
        # Authentication stuff
        request = FedexRequest(self.get_debug_logger_xml(picking), request_type="validating",
                               prod_environment=shipping_account.prod_environment)
        request.web_authentication_detail(shipping_account.fedex_developer_key,
                                          shipping_account.fedex_developer_password)
        request.client_detail(shipping_account.fedex_account_number,
                              shipping_account.fedex_meter_number)
        request.add_address_to_validation_request(delivery_address)
        return request.process_validation(delivery_address)
