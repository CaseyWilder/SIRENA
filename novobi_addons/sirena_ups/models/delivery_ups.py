# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.
import logging

from odoo import api, fields, models, tools, _
from odoo.addons.omni_ups.models.ups_request import UPSRequest
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT
from odoo.tools import pdf
from datetime import datetime

_logger = logging.getLogger(__name__)


class DeliveryCarrier(models.Model):
    _inherit = 'delivery.carrier'

    @api.model
    def ups_create_shipment_label(self, picking, product_packaging,
                                  package_length, package_width, package_height, weight,
                                  pickup_date, shipping_options, label_options, delivery_options, insurance_options,
                                  is_return=False):
        shipping_account = picking.shipping_account_id
        UPS = UPSRequest(debug_logger=self.get_debug_logger_json(picking),
                         username=shipping_account.ups_username, password=shipping_account.ups_passwd,
                         access_number=shipping_account.ups_access_number,
                         prod_environment=shipping_account.prod_environment)

        invoice_line_total = 0
        for move in picking.move_lines:
            invoice_line_total += picking.company_id.currency_id.round(move.product_id.lst_price * move.product_qty)

        # Time format is "%H%M%S", set value of time is 12:00:00
        ship_datetime = {
            'date': pickup_date.strftime('%Y-%m-%d'),
            'time': '12:00:00'
        }

        handling_fee = picking.handling_fee

        if not picking.is_mul_packages:
            package_detail = [{
                'packaging': product_packaging.shipper_package_code or '02',
                'length': package_length,
                'width': package_width,
                'height': package_height,
                'weight': weight if picking.ups_service_type != '92' else picking.package_shipping_weight_oz,
            }]
        else:
            package_detail = [{
                'packaging': picking_package.packaging_id.shipper_package_code or '02',
                'length': picking_package.length,
                'width': picking_package.width,
                'height': picking_package.height,
                'weight': picking_package.weight if picking.ups_service_type != '92' else picking_package.weight_oz,
            } for picking_package in picking.picking_package_ids]
            handling_fee = sum([p.handling_fee for p in picking.picking_package_ids])

        insurance_detail = None
        if insurance_options.get('insurance_amount') and not picking.is_mul_packages:
            insurance_detail = {
                'insurance_amount': insurance_options['insurance_amount'],
                'currency': picking.partner_id.country_id.currency_id.name,
            }

        shipment_options = {
            "non_machinable": picking.shipping_non_machinable,
            "additional_handling": picking.shipping_require_additional_handling,
            "change_billing": {
                "account": picking.shipping_customer_account,
                "zipcode": picking.shipping_customer_zipcode,
            } if picking.shipping_change_billing else None,
            "alcohol": picking.shipping_include_alcohol
        }
        if not label_options:
            label_options = {
                "return_label": picking.shipping_include_return_label,
                "bill_duty_and_tax": picking.shipping_bill_duty_and_tax,
                "dry_ice": {
                    "weight": picking.shipping_dry_ice_weight_in_oz,
                } if picking.shipping_include_dry_ice else None,
            }
        else:
            label_options.update({
                "return_label": picking.shipping_include_return_label,
                "bill_duty_and_tax": picking.shipping_bill_duty_and_tax,
                "dry_ice": {
                    "weight": picking.shipping_dry_ice_weight_in_oz,
                } if picking.shipping_include_dry_ice else None,
            })

        if not delivery_options:
            delivery_options = {
                "cod": {
                    "type": picking.shipping_cod_payment_type,
                    "amount": picking.shipping_cod_amount,
                } if picking.shipping_cod else None,
                "saturday_delivery": picking.shipping_saturday_delivery,
                "optional_signature": picking.shipping_optional_signature,
            }
        else:
            delivery_options.update({
                "cod": {
                    "type": picking.shipping_cod_payment_type,
                    "amount": picking.shipping_cod_amount,
                } if picking.shipping_cod else None,
                "saturday_delivery": picking.shipping_saturday_delivery,
                "optional_signature": picking.shipping_optional_signature,
            })

        references = [{'value': picking.get_origin(), 'code': 'TN'},
                      {'value': datetime.now().strftime("%m/%d/%Y"), 'code': 'TN'}]

        result = UPS.create_shipment_label(
            shipper_number=shipping_account.ups_shipper_number,
            package_detail=package_detail,
            shipper=picking.company_id.partner_id,
            ship_from=picking.picking_type_id.warehouse_id.partner_id,
            ship_to=picking.partner_id,
            service_type=self.ups_default_service_type,
            insurance_detail=insurance_detail,
            confirmation=picking.ups_shipping_confirmation,
            shipping_info={
                'shipment_options': shipment_options,
                'label_options': label_options,
                'delivery_options': delivery_options,
                'label_stock_type': shipping_account.ups_label_stock_type
            },
            label_file_type=self.ups_label_file_type,
            is_return=is_return,
            is_residential=picking.is_residential_address,
            references=references
        )

        if 'errors' in result:
            errors = result['errors']
            if isinstance(errors, dict):
                errors = [errors]
            error_message = ', '.join(str(error.get('error_message')) for error in errors)
            if not is_return:
                return {'success': False,
                        'price': False,
                        'tracking_number': False,
                        'error_message': _(error_message),
                        'warning_message': False}
            else:
                title = 'Cannot create return label !'
                exceptions = [{'title': 'Message from UPS',
                               'reason': _(error_message)}]
                picking._log_exceptions_on_picking(title, exceptions)
                return True
        elif 'price' not in result:
            return dict(success=False, error_message=_('Cannot connect to UPS Server. Please try again later!'))

        order = picking.sale_id
        company = order.company_id or picking.company_id or self.env.company
        currency_order = picking.sale_id.currency_id
        if not currency_order:
            currency_order = picking.company_id.currency_id

        if currency_order.name == result['currency_code']:
            price = float(result['price']) + handling_fee
            price_without_discounts = float(result.get('price_without_discounts', 0.0))
            if price_without_discounts > 0:
                price_without_discounts += handling_fee
        else:
            ResCurrency = self.env['res.currency']
            quote_currency = ResCurrency.search([('name', '=', result['currency_code'])], limit=1)
            price = quote_currency._convert(
                float(result['price']) + handling_fee, currency_order, company, order.date_order or fields.Date.today())

            price_without_discounts = quote_currency._convert(
                float(result.get('price_without_discounts', 0.0)), currency_order, company,
                order.date_order or fields.Date.today())
            if price_without_discounts > 0:
                price_without_discounts += handling_fee
        package_labels = [(track_number, label_binary_data)
                          for track_number, label_binary_data in result.get('label_binary_data').items()]

        carrier_tracking_ref = result.get('tracking_ref', '')
        if not is_return:
            logmessage = _("Shipment created into UPS<br/>"
                           "<b>Tracking Number:</b> %s<br/>") % carrier_tracking_ref

            if self.ups_label_file_type == 'GIF':
                attachments = [
                    ('LabelUPS-%s.pdf' % carrier_tracking_ref, pdf.merge_pdf([pl[1] for pl in package_labels]))]
            else:
                attachments = [('LabelUPS-%s.%s' % (pl[0], self.ups_label_file_type), pl[1]) for pl in package_labels]
        else:
            logmessage = _("Return label generated<br/>"
                           "<b>Tracking Numbers:</b> %s<br/>") % carrier_tracking_ref
            if self.ups_label_file_type == 'GIF':
                attachments = [(
                    '%s-%s-%s.%s' % (self.get_return_label_prefix(), carrier_tracking_ref, 1, 'pdf'),
                    pdf.merge_pdf([pl[1] for pl in package_labels])
                )]
            else:
                attachments = [
                    ('%s-%s-%s.%s' % (self.get_return_label_prefix(), pl[0], index, self.ups_label_file_type), pl[1])
                    for index, pl in enumerate(package_labels)
                ]

        picking.message_post(body=logmessage, attachments=attachments)
        # Get estimated_date from UPS
        time_in_transit_response = UPS.get_time_in_transit(
            weight=weight,
            service_type=self.ups_default_service_type,
            ship_from=picking.picking_type_id.warehouse_id.partner_id,
            ship_to=picking.partner_id,
            ship_datetime=ship_datetime,
            insurance_detail=insurance_detail,
            saturday_delivery=picking.shipping_saturday_delivery,
        )

        estimated_date = 'N/A'
        if isinstance(time_in_transit_response.get('estimated_date', False), str):
            ups_datetime = time_in_transit_response['estimated_date']
            try:
                estimated_date = datetime.strptime(ups_datetime, '%Y-%m-%d').strftime(DEFAULT_SERVER_DATE_FORMAT)
            except ValueError:
                pass

        shipping_data = {
            'success': True,
            'price': price,
            'price_without_discounts': price_without_discounts,
            'insurance_cost': False,
            'carrier_tracking_ref': carrier_tracking_ref,
            'package_carrier_tracking_ref': [pl[0] for pl in package_labels],
            'estimated_date': estimated_date,
            'error_message': False,
            'warning_message': False
        }

        if not is_return and picking.shipping_include_return_label:
            self.ups_create_shipment_label(
                picking, product_packaging, package_length, package_width, package_height, weight,
                pickup_date, shipping_options, label_options, delivery_options, insurance_options, True)

        return shipping_data
