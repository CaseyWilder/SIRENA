# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

import logging
from odoo import api, fields, models, _
from odoo.exceptions import UserError

from .shipping_method_mixin import USPS_FIRST_CLASS_MAIL_TYPE_SELECTION, USPS_CONTAINER_SELECTION

_logger = logging.getLogger(__name__)


class ShippingMethodChannel(models.Model):
    _name = 'shipping.method.channel'
    _inherit = 'shipping.method.mixin'
    _description = 'Shipping Method on each Channel'

    # Mixin selection fields
    usps_first_class_mail_type = fields.Selection(store=True)
    usps_container = fields.Selection(store=True)

    name = fields.Char('Requested Service', required=True, index=True)
    package_type = fields.Char('Type of Package', compute='_compute_package_type')
    active = fields.Boolean('Active', default=True, copy=False)

    def _compute_package_type(self):
        def get_ups_package_type():
            default_packaging_id = record.default_packaging_id
            return default_packaging_id.name if default_packaging_id else ''

        def get_fedex_package_type():
            default_packaging_id = record.default_packaging_id
            return default_packaging_id.name if default_packaging_id else ''

        def get_usps_package_type():
            if record.usps_is_first_class:
                mail_type = record.usps_first_class_mail_type
                l = list(filter(lambda s: s[0] == mail_type, USPS_FIRST_CLASS_MAIL_TYPE_SELECTION))
            else:
                container = record.usps_container
                l = list(filter(lambda s: s[0] == container, USPS_CONTAINER_SELECTION))
            return l[0][1] if l else ''

        for record in self:
            provider = record.provider
            if provider == 'ups':
                record.package_type = get_ups_package_type()
            elif provider == 'fedex':
                record.package_type = get_fedex_package_type()
            elif provider == 'usps':
                record.package_type = get_usps_package_type()
            else:
                record.package_type = ''
