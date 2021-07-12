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

FEDEX_SMARTPOST_INDICIA_SELECTION = [
    ('MEDIA_MAIL', 'Media Mail'),
    ('PRESORTED_BOUND_PRINTED_MATTER', 'Bound Printed Matter'),
    ('PRESORTED_STANDARD', 'Parcel Select Lightweight / Standard Mail'),
    ('PARCEL_SELECT', 'Parcel Select'),
    ('PARCEL_RETURN', 'Parcel Return')
]

FEDEX_SMARTPOST_HUBID_SELECTION = [
    ('5185', '5185 - Allentown, Pennsylvania'),
    ('5303', '5303 - Atlanta, Georgia'),
    ('5213', '5213 - Baltimore, Maryland'),
    ('5281', '5281 - Charlotte, North Carolina'),
    ('5929', '5929 - Chino, California'),
    ('5751', '5751 - Dallas, Texas'),
    ('5802', '5802 - Denver, Colorado'),
    ('5481', '5481 - Detroit, Michigan'),
    ('5087', '5087 - Edison, New Jersey'),
    ('5431', '5431 - Grove City, Ohio'),
    ('5771', '5771 - Houston, Texas'),
    ('5436', '5436 - Groveport, Ohio'),
    ('5902', '5902 - Los Angeles, California'),
    ('5465', '5465 - Idianapolis, Indiana'),
    ('5648', '5648 - Kansas City, Kansas'),
    ('5254', '5254 - Martinsburg, West Virginia'),
    ('5183', '5183 - Macungie, Pennsylvania'),
    ('5379', '5379 - Memphis, Tennessee'),
    ('5552', '5552 - Minneapolis, Minnesota'),
    ('5531', '5531 - New Berlin, Wisconsin (test environment\'s only valid value)'),
    ('5110', '5110 - Newburgh, New York'),
    ('5095', '5095 - Newark, New Jersey'),
    ('5015', '5015 - Northborough, Massachusetts'),
    ('5327', '5327 - Orlando, Florida'),
    ('5194', '5194 - Philadelphia, Pennsylvania'),
    ('5854', '5854 - Phoenix, Arizona'),
    ('5150', '5150 - Pittsburgh, Pennsylvania'),
    ('5958', '5958 - Sacramento, California'),
    ('5097', '5097 - South Brunswick, New Jersey'),
    ('5186', '5186 - Scranton, Pennsylvania'),
    ('5843', '5843 - Salt Lake City, Utah'),
    ('5983', '5983 - Seattle, Washington'),
    ('5631', '5631 - St. Louis, Missouri'),
    ('5893', '5893 - Reno, Nevada'),
    ('5345', '5345 - Tampa, Florida'),
    ('5602', '5602 - Wheeling, Illinois'),
    ('5061', '5061 - Windsor, Connecticut'),
]

FEDEX_SMARTPOST_ANCILLARY_SELECTION = [
    ('NONE', 'No Ancillary Endorsement'),
    ('ADDRESS_CORRECTION', 'Address Correction'),
    ('CARRIER_LEAVE_IF_NO_RESPONSE', 'Carrier Leave If No Response'),
    ('CHANGE_SERVICE', 'Change Service'),
    ('FORWARDING_SERVICE', 'Forwarding Service'),
    ('RETURN_SERVICE', 'Return Service')
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

    smartpost_indicia = fields.Selection(FEDEX_SMARTPOST_INDICIA_SELECTION, string='SmartPost Indicia',
                                         default='PARCEL_SELECT')
    smartpost_hubId = fields.Selection(FEDEX_SMARTPOST_HUBID_SELECTION, string='SmartPost HubID', default='5531')
    smartpost_ancillary = fields.Selection(FEDEX_SMARTPOST_ANCILLARY_SELECTION,
                                           string='SmartPost Ancillary Endorsement', default='NONE')
    fedex_service_type = fields.Selection(related='delivery_carrier_id.fedex_service_type')

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
            # Set/unset residential for some specific FedEx shipping services.
            'is_residential_address': self.delivery_carrier_id.fedex_service_type == 'GROUND_HOME_DELIVERY',
        })
