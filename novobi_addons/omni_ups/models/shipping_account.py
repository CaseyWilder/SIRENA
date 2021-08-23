# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

import logging
from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)

class ShippingAccount(models.Model):
    _inherit = 'shipping.account'

    UPS_FIELDS = ['ups_username', 'ups_passwd', 'ups_shipper_number', 'ups_access_number']

    provider = fields.Selection(selection_add=[('ups', 'UPS')], ondelete={'ups': 'set default'})

    ups_username = fields.Char(string='UPS Username', groups="base.group_system")
    ups_passwd = fields.Char(string='UPS Password', groups="base.group_system")
    ups_shipper_number = fields.Char(string='UPS Shipper Number', groups="base.group_system")
    ups_access_number = fields.Char(string='UPS Access License Number', groups="base.group_system")

    @api.model
    def _get_logo_url(self):
        url = super(ShippingAccount, self)._get_logo_url()
        if self.provider == 'ups':
            url = '/omni_ups/static/src/img/ups.png'
        return url

    @api.model
    def ups_create_services(self):
        vals_list = []
        for service in self.env['delivery.carrier']._get_ups_service_types():
            vals_list.append({
                'ups_username': self['ups_username'],
                'ups_passwd': self['ups_passwd'],
                'ups_shipper_number': self['ups_shipper_number'],
                'ups_access_number': self['ups_access_number'],
                'name': service[1],
                'product_id': self.env.ref('delivery_ups.product_product_delivery_ups_be').id,
                'ups_default_service_type': service[0],
                'delivery_type': 'ups',
                'shipping_account_id': self.id
            })
        carriers = self.env['delivery.carrier'].sudo().create(vals_list)
        self.sudo().write({
            'delivery_carrier_ids': [(6, 0, carriers.ids)]
        })

    @api.model
    def _get_credential_fields(self):
        credentials = super(ShippingAccount, self)._get_credential_fields()
        credentials.extend(self.UPS_FIELDS)
        return credentials

    def _update_services(self):
        self.ensure_one()
        vals_list = []
        services = self.env['delivery.carrier']._get_ups_service_types()
        for service in services:
            if not self.delivery_carrier_ids.filtered(lambda e: e.ups_default_service_type == service[0]):
                vals_list.append({
                    'ups_username': self['ups_username'],
                    'ups_passwd': self['ups_passwd'],
                    'ups_shipper_number': self['ups_shipper_number'],
                    'ups_access_number': self['ups_access_number'],
                    'name': service[1],
                    'product_id': self.env.ref('delivery_ups.product_product_delivery_ups_be').id,
                    'ups_default_service_type': service[0],
                    'delivery_type': 'ups',
                    'shipping_account_id': self.id
                })
        if vals_list:
            carriers = self.env['delivery.carrier'].sudo().create(vals_list)
            self.sudo().write({
                'delivery_carrier_ids': [(4, carrier.id) for carrier in carriers]
            })

    def _ups_update_label_file_type(self):
        type_selection_mapping = {
            'PDF': 'GIF',
            'ZPL': 'ZPL',
        }
        for record in self:
            file_type = type_selection_mapping.get(record.label_file_type, 'GIF')
            record.delivery_carrier_ids.write(dict(ups_label_file_type=file_type))
