# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

import logging
from odoo import api, fields, models


_logger = logging.getLogger(__name__)


USPS_FIRST_CLASS_MAIL_TYPE_SELECTION = [
    ('LETTER', 'Letter'),
    ('FLAT', 'Flat'),
    ('PARCEL', 'Parcel'),
    ('POSTCARD', 'Postcard'),
    ('PACKAGE SERVICE RETAIL', 'Package Service Retail')
]

USPS_CONTAINER_SELECTION = [
    ('VARIABLE', 'Regular < 12 inch'),
    ('RECTANGULAR', 'Rectangular'),
    ('NONRECTANGULAR', 'Non-rectangular')
]


class ShippingMethodMixin(models.AbstractModel):
    _name = 'shipping.method.mixin'
    _description = 'Shipping Method Mixin'

    shipping_account_id = fields.Many2one('shipping.account',
                                          string='Shipping Account', ondelete='cascade', copy=False)
    shipping_account_delivery_carrier_ids = fields.Many2many(related='shipping_account_id.delivery_carrier_ids',
                                                             string='Shipping Services', copy=False)
    provider = fields.Char(string='Provider', store=True, compute='_get_provider', copy=False)
    delivery_carrier_id = fields.Many2one('delivery.carrier', string="Shipping Service",
                                          domain="[('shipping_account_id.id', '=', shipping_account_id)]", copy=False)
    default_packaging_id = fields.Many2one('product.packaging',
                                           string='Package Type',
                                           domain="['|', ('package_carrier_type', '=', provider), ('is_custom', '=', True)]",
                                           copy=False)
    usps_is_first_class = fields.Boolean('Is USPS First Class',
                                         compute='_compute_usps_is_first_class', copy=False)
    # Avoid error while updating selection field -> let store=False
    usps_first_class_mail_type = fields.Selection(USPS_FIRST_CLASS_MAIL_TYPE_SELECTION, string="USPS First Class Mail Type",
                                                  store=False, copy=False)

    # Avoid error while updating selection field -> let store=False
    usps_container = fields.Selection(USPS_CONTAINER_SELECTION, string="USPS Type of container", store=False, copy=False)

    package_type = fields.Char(string='Package Type', compute='_get_package_type', store=True, copy=False)

    is_residential_address = fields.Boolean(string='Residential')

    @api.depends('default_packaging_id', 'usps_is_first_class', 'usps_first_class_mail_type', 'usps_container')
    def _get_package_type(self):
        for record in self:
            if record.provider == 'usps':
                if record.usps_is_first_class:
                    record.package_type = record.usps_first_class_mail_type
                else:
                    record.package_type = record.usps_container
            else:
                record.package_type = record.default_packaging_id.name

    @api.depends('shipping_account_id', 'shipping_account_id.provider')
    def _get_provider(self):
        for record in self:
            record.provider = record.shipping_account_id.provider

    @api.depends('provider', 'delivery_carrier_id')
    def _compute_usps_is_first_class(self):
        for record in self:
            if record.provider == 'usps':
                if record.delivery_carrier_id.name == 'First Class':
                    record.usps_is_first_class = True
                else:
                    record.usps_is_first_class = False
            else:
                record.usps_is_first_class = False

    @api.onchange('shipping_account_id')
    def onchange_shipping_account(self):
        self.delivery_carrier_id = False
        self.onchange_delivery_carrier_id()

    @api.onchange('delivery_carrier_id')
    def onchange_delivery_carrier_id(self):
        self.update({
            'default_packaging_id': False,
            'usps_first_class_mail_type': False,
            'usps_container': False,
        })
