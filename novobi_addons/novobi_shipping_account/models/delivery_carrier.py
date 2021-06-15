# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

import logging
import re
import json
from lxml import etree

from odoo import api, fields, models, registry, _
from odoo.tools import html_escape

_logger = logging.getLogger(__name__)


class DeliveryCarrier(models.Model):
    _inherit = 'delivery.carrier'

    product_id = fields.Many2one('product.product', required=False)

    def get_carrier(self, display=False):
        self.ensure_one()
        if display:
            providers_dict = dict(self._fields['delivery_type'].selection)
            return providers_dict.get(self.delivery_type, False)
        return self.delivery_type

    @api.model
    def create_shipment_label(self, picking, product_packaging,
                              package_length, package_width, package_height, weight, insurance_options,
                              pickup_date, shipping_options, label_options, delivery_options):

        """
        Create label
        :return: {
                    'success': Bool,
                    'price': Float,
                    'estimated_date': String,
                    'error_message': String,
                    'warning_message': String,
                 }
        """
        cust_method_name = '%s_create_shipment_label' % self.delivery_type
        if hasattr(self, cust_method_name):
            method = getattr(self, cust_method_name)(picking=picking, product_packaging=product_packaging,
                                                     package_length=package_length, package_width=package_width,
                                                     package_height=package_height, weight=weight,
                                                     pickup_date=pickup_date, shipping_options=shipping_options,
                                                     delivery_options=delivery_options, label_options=label_options,
                                                     insurance_options=insurance_options)
            return method
        return {'success': False, 'error_message': "Cannot create label at this time, please try again later!"}

    @api.model
    def get_rate_and_delivery_time(self, picking, product_packaging,
                                   package_length, package_width, package_height, weight,
                                   pickup_date, shipping_options, insurance_amount):
        """
        Get rate for shipment
        :return: {
                    'success': Bool,
                    'price': Float,
                    'estimated_date': String,
                    'error_message': String,
                    'warning_message': String,
                 }
        """
        cust_method_name = '%s_get_rate_and_delivery_time' % self.delivery_type
        if hasattr(self, cust_method_name):
            method = getattr(self.sudo(), cust_method_name)(picking=picking, product_packaging=product_packaging,
                                                            package_length=package_length, package_width=package_width,
                                                            package_height=package_height, weight=weight,
                                                            pickup_date=pickup_date, shipping_options=shipping_options,
                                                            insurance_amount=insurance_amount)
            return method
        return {'success': False, 'error_message': "Cannot get rate at this time, please try again later!"}

    def check_shipment_status(self, pickings):
        """
        Get shipment status from carrier
        """
        self.ensure_one()

        cust_method_name = 'check_%s_shipment_status' % self.delivery_type
        if hasattr(self, cust_method_name):
            method = getattr(self.sudo(), cust_method_name)
            return method(pickings)
        return {'success': False, 'error_message': 'Cannot Tracking info at this time, please try again later!'}

    @api.model
    def void_label(self, picking):
        """
        Void label
        :return: {
                    'success': Bool,
                    'error_message': String,
                    'warning_message': String,
                }
        """
        cust_method_name = '%s_void_label' % self.delivery_type
        if hasattr(self, cust_method_name):
            return getattr(self.sudo(), cust_method_name)(picking=picking)
        return {'success': False, 'error_message': "Cannot void label at this time, please try again later!"}

    def get_debug_logger_json(self, picking):
        def recursive_trim_list(array):
            for i, v in enumerate(array):
                if isinstance(v, str):
                    if len(v) > 75 and (len(re.findall(r"[\s.,]", v)) / len(v)) < 0.05:
                        array[i] = v[:72] + '...'
                    elif len(v) > 300:
                        array[i] = v[:297] + '...'
                else:
                    recursive_trim(v)

        def recursive_trim_dict(dictionary):
            for k, v in dictionary.items():
                if isinstance(v, str):
                    if len(v) > 75 and (len(re.findall(r"[\s.,]", v)) / len(v)) < 0.05:
                        dictionary[k] = v[:72] + '...'
                    elif len(v) > 300:
                        dictionary[k] = v[:297] + '...'
                else:
                    recursive_trim(v)

        def recursive_trim(data):
            if isinstance(data, dict):
                recursive_trim_dict(data)
            elif isinstance(data, list):
                recursive_trim_list(data)

        def debug_logger(json_string, func):
            try:
                content = str(json_string, 'utf-8')
            except TypeError:
                content = json_string

            try:
                data = json.loads(content)
            except json.decoder.JSONDecodeError:
                data = dict(content=content)
            recursive_trim(data)
            content = json.dumps(data, indent=2)
            mess = '<p>{description}:</p><p><pre>{content}</pre></p>'.format(
                description=func,
                content=content
            )
            picking.message_post(body=mess)

        if len(self) == 1 and self.debug_logging and picking:
            return debug_logger
        return lambda x, y: None

    def get_debug_logger_xml(self, picking):
        def debug_logger(xml_string, func):
            if picking:
                try:
                    content = etree.tostring(xml_string)
                except TypeError:
                    content = xml_string
                try:
                    content = str(content, 'utf-8')
                except TypeError:
                    content = xml_string
                content = re.sub(r'\s+', ' ', content)
                content = re.sub(r'> <', r'><', content)

                root = etree.fromstring(content.encode('utf-8'))
                for element in root.iter():
                    t = element.text
                    if t:
                        if len(t) > 75 and (len(re.findall(r"[\s.,]", t)) / len(t)) < 0.05:
                            element.text = t[:72] + '...'
                        elif len(t) > 300:
                            element.text = t[:297] + '...'

                content = etree.tostring(root, pretty_print=True)
                content = str(content, 'utf-8')
                content = content.strip()
                content = html_escape(content)
                mess = '<p>{description}:</p><p><pre>{content}</pre></p>'.format(
                    description=func,
                    content=content
                )
                picking.message_post(body=mess)

        if len(self) == 1 and self.debug_logging and picking:
            return debug_logger
        return lambda x, y: None
