# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

import logging
from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)

FEDEX_SERVICES = [('FEDEX_GROUND', 'FedEx Ground®'),
                  ('FEDEX_2_DAY', 'FedEx 2Day®'),
                  ('FEDEX_2_DAY_AM', 'FedEx 2Day® A.M.'),
                  ('FEDEX_3_DAY_FREIGHT', 'FedEx 3Day® Freight'),
                  ('FIRST_OVERNIGHT', 'FedEx First Overnight®'),
                  ('PRIORITY_OVERNIGHT', 'FedEx Priority Overnight®'),
                  ('STANDARD_OVERNIGHT', 'FedEx Standard Overnight®'),
                  ('FEDEX_NEXT_DAY_EARLY_MORNING', 'FedEx Next Day® Early Morning'),
                  ('FEDEX_NEXT_DAY_MID_MORNING', 'FedEx Next Day® Mid Morning'),
                  ('FEDEX_NEXT_DAY_AFTERNOON', 'FedEx Next Day® Afternoon'),
                  ('FEDEX_NEXT_DAY_END_OF_DAY', 'FedEx Next Day® End Of Day'),
                  ('INTERNATIONAL_ECONOMY', 'FedEx International Economy®'),
                  ('INTERNATIONAL_PRIORITY', 'FedEx International Priority®'),
                   ]


class ShippingAccount(models.Model):
    _inherit = 'shipping.account'

    FEDEX_FIELDS = ['fedex_developer_key', 'fedex_developer_password', 'fedex_account_number', 'fedex_meter_number']

    provider = fields.Selection(selection_add=[('fedex', 'FedEx')], ondelete={'fedex': 'set default'})

    fedex_developer_key = fields.Char(string="Developer Key", groups="base.group_system")
    fedex_developer_password = fields.Char(string="Password", groups="base.group_system")
    fedex_account_number = fields.Char(string="FedEx Account Number", groups="base.group_system")
    fedex_meter_number = fields.Char(string="Meter Number", groups="base.group_system")

    @api.model
    def _get_logo_url(self):
        url = super(ShippingAccount, self)._get_logo_url()
        if self.provider == 'fedex':
            url = '/omni_fedex/static/src/img/fedex.png'
        return url

    @api.model
    def fedex_create_services(self):
        vals_list = []
        for service in FEDEX_SERVICES:
            vals_list.append({
                'fedex_developer_key': self['fedex_developer_key'],
                'fedex_developer_password': self['fedex_developer_password'],
                'fedex_account_number': self['fedex_account_number'],
                'fedex_meter_number': self['fedex_meter_number'],
                'name': service[1],
                'product_id': self.env.ref('delivery_fedex.product_product_delivery_fedex_us').id,
                'fedex_service_type': service[0],
                'delivery_type': 'fedex',
                'shipping_account_id': self.id
            })
        carriers = self.env['delivery.carrier'].sudo().create(vals_list)
        self.sudo().write({
            'delivery_carrier_ids': [(6, 0, carriers.ids)]
        })

    @api.model
    def _get_credential_fields(self):
        credentials = super(ShippingAccount, self)._get_credential_fields()
        credentials.extend(self.FEDEX_FIELDS)
        return credentials