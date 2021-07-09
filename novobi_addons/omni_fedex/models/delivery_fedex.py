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

    fedex_service_type = fields.Selection([('INTERNATIONAL_ECONOMY', 'INTERNATIONAL_ECONOMY'),
                                           ('INTERNATIONAL_PRIORITY', 'INTERNATIONAL_PRIORITY'),
                                           ('FEDEX_GROUND', 'FEDEX_GROUND'),
                                           ('GROUND_HOME_DELIVERY', 'GROUND_HOME_DELIVERY'),
                                           ('SMART_POST', 'SMART_POST'),
                                           ('FEDEX_2_DAY', 'FEDEX_2_DAY'),
                                           ('FEDEX_2_DAY_AM', 'FEDEX_2_DAY_AM'),
                                           ('FEDEX_3_DAY_FREIGHT', 'FEDEX_3_DAY_FREIGHT'),
                                           ('FIRST_OVERNIGHT', 'FIRST_OVERNIGHT'),
                                           ('PRIORITY_OVERNIGHT', 'PRIORITY_OVERNIGHT'),
                                           ('STANDARD_OVERNIGHT', 'STANDARD_OVERNIGHT'),
                                           ('FEDEX_NEXT_DAY_EARLY_MORNING', 'FEDEX_NEXT_DAY_EARLY_MORNING'),
                                           ('FEDEX_NEXT_DAY_MID_MORNING', 'FEDEX_NEXT_DAY_MID_MORNING'),
                                           ('FEDEX_NEXT_DAY_AFTERNOON', 'FEDEX_NEXT_DAY_AFTERNOON'),
                                           ('FEDEX_NEXT_DAY_END_OF_DAY', 'FEDEX_NEXT_DAY_END_OF_DAY'),
                                           ('FEDEX_EXPRESS_SAVER', 'FEDEX_EXPRESS_SAVER'),
                                           ],
                                          default='INTERNATIONAL_PRIORITY')

    def _fedex_convert_weight_in_ob(self, weight, unit='LB'):
        weight_uom_id = self.env.ref('uom.product_uom_lb')
        if unit == 'KG':
            weight_value = weight_uom_id._compute_quantity(weight, self.env.ref('uom.product_uom_kgm'), round=False)
        elif unit == 'LB':
            weight_value = weight
        else:
            raise ValueError
        return max(weight_value, 0.01) if weight_value <= 0.0 else weight_value

    @api.model
    def _fedex_convert_cost(self, order_id, company_id, response_type):
        order_currency = order_id.currency_id
        company_currency = company_id.currency_id
        if _convert_curr_iso_fdx(order_currency.name) in response_type:
            cost = response_type[_convert_curr_iso_fdx(order_currency.name)]
        else:
            _logger.info("Preferred currency has not been found in FedEx response")
            if _convert_curr_iso_fdx(company_currency.name) in response_type:
                amount = response_type[_convert_curr_iso_fdx(company_currency.name)]
            else:
                amount = response_type.get('USD', 0.0)
            if isinstance(amount, Decimal):
                amount = float(amount)
            cost = company_currency._convert(
                amount, order_currency, company_id, order_id.date_order or fields.Date.today())
        return cost

    @api.model
    def fedex_check_connection(self, shipping_account):
        self += self.env.ref('omni_fedex.fedex_fedex_2_day')
        product_packaging = self.env.ref('delivery_fedex.fedex_packaging_FEDEX_BOX')

        shipper = self.env.ref('novobi_shipping_account.shipper_test_connection')
        warehouse = self.env.ref('novobi_shipping_account.ship_from_test_connection')
        recipient = self.env.ref('novobi_shipping_account.ship_to_test_connection')

        weight_value = self._fedex_convert_weight_in_ob(weight=5)
        # Authentication stuff
        request = FedexRequest(self.get_debug_logger_xml(None), request_type="rating",
                               prod_environment=shipping_account.prod_environment)
        request.web_authentication_detail(shipping_account.fedex_developer_key,
                                          shipping_account.fedex_developer_password)
        request.client_detail(shipping_account.fedex_account_number, shipping_account.fedex_meter_number)

        request.transaction_detail("Check Connection")
        request.shipment_request(
            self.fedex_droppoff_type,
            self.fedex_service_type,
            product_packaging.shipper_package_code,
            self.fedex_weight_unit,
        )

        request.set_currency(_convert_curr_iso_fdx("USD"))
        request.set_shipper(shipper, warehouse)
        request.set_recipient(recipient)

        request._add_package(
            weight_value=weight_value,
            package_code=product_packaging.shipper_package_code,
            package_dimension=dict(height=10, width=20, length=30),
            mode='rating',
        )
        request.set_master_package(weight_value, 1)

        response = request.rate()

        error_message = False
        if response.get('errors_message'):
            error_message = response['errors_message']
        return {'error_message': error_message}

    @api.model
    def fedex_get_rate_and_delivery_time(self, picking, product_packaging,
                                         package_length, package_width, package_height, weight,
                                         pickup_date, shipping_options, insurance_amount, **kw):

        shipping_account = self.shipping_account_id
        package_type = product_packaging.shipper_package_code or 'YOUR_PACKAGING'
        shipper = picking.company_id.partner_id
        warehouse = picking.picking_type_id.warehouse_id.partner_id
        recipient = picking.partner_id
        residential = picking.is_residential_address
        is_india = recipient.country_id.code == 'IN' and shipper.country_id.code == 'IN'

        pickup_datetime = datetime.datetime.combine(pickup_date, datetime.time(12, 0, 0))
        order_currency = picking.sale_id.currency_id or picking.company_id.currency_id
        company_currency = picking.company_id.currency_id

        advanced_options = {
            # 'shipping_change_billing': picking.shipping_change_billing,
            'shipping_include_return_label': picking.shipping_include_return_label,
            'shipping_saturday_delivery': picking.shipping_saturday_delivery,
            'shipping_cod': picking.shipping_cod
        }

        advanced_option_values = {
            'cod_payment_type': 'ANY' if picking.shipping_cod_payment_type == 'any' else 'CASH' if picking.shipping_cod_payment_type == 'cash' else 'COMPANY_CHECK',
            'cod_amount': picking.shipping_cod_amount,
        }
        # Authentication stuff
        request = FedexRequest(self.get_debug_logger_xml(picking), request_type="rating",
                               prod_environment=shipping_account.prod_environment)
        request.web_authentication_detail(shipping_account.fedex_developer_key,
                                          shipping_account.fedex_developer_password)
        request.client_detail(shipping_account.fedex_account_number,
                              shipping_account.fedex_meter_number)

        # Build basic rating request and set addresses
        request.transaction_detail(picking.name)

        request.shipment_request(
            dropoff_type=self.fedex_droppoff_type,
            service_type=self.fedex_service_type,
            packaging_type=package_type,
            overall_weight_unit=self.fedex_weight_unit,
            pickup_datetime=pickup_datetime
        )

        request.set_currency(_convert_curr_iso_fdx(order_currency.name))

        request.shipment_request_special_services(advanced_options=advanced_options,
                                                  advanced_option_values=advanced_option_values)
        request.set_pickup_detail(pickup_datetime)

        if not picking.is_mul_packages:
            request.set_insured_amount(amount=insurance_amount)

        request.set_shipper(shipper, warehouse)
        request.set_recipient(recipient)
        request.set_residential(residential)

        if not picking.is_mul_packages:
            weight_value = self._fedex_convert_weight_in_ob(weight, unit=self.fedex_weight_unit)
            package_dimension = dict(height=package_height, width=package_width, length=package_length)

            request._add_package(
                weight_value=weight_value,
                package_code=package_type,
                package_dimension=package_dimension,
                confirmation=picking.fedex_shipping_confirmation,
                mode='rating',
                insurance_amount=insurance_amount,
                handling_fee=picking.handling_fee
            )
            request.set_master_package(weight_value, 1)
        else:
            total_weight = 0.0
            for sequence, pkg in enumerate(picking.picking_package_ids, start=1):
                weight_value = self._fedex_convert_weight_in_ob(pkg.weight, unit=self.fedex_weight_unit)
                request._add_package(
                    weight_value=weight_value,
                    package_code=pkg.packaging_id.shipper_package_code,
                    package_dimension=dict(width=pkg.width, height=pkg.height, length=pkg.length),
                    confirmation=picking.fedex_shipping_confirmation,
                    mode='rating',
                    sequence_number=sequence,
                    insurance_amount=insurance_amount,
                    handling_fee=pkg.handling_fee
                )
                total_weight += weight_value
            request.set_master_package(total_weight, len(picking.picking_package_ids))

        # Set shipping charge payment
        shipping_charge_payment_account = shipping_account.fedex_account_number
        shipping_charge_payment_type = 'SENDER'
        bill_duties_party = warehouse
        if advanced_options.get('shipping_change_billing'):
            shipping_charge_payment_account = picking.shipping_customer_account
            shipping_charge_payment_type = 'RECIPIENT'
            bill_duties_party = recipient

        request._shipping_charges_payment(shipping_charge_payment_account, shipping_charge_payment_type)

        # Commodities for customs declaration (international shipping)
        if self.fedex_service_type in ['INTERNATIONAL_ECONOMY', 'INTERNATIONAL_PRIORITY'] or is_india:
            total_commodities_amount = 0.0
            commodity_country_of_manufacture = warehouse.country_id.code
            for line in picking.move_lines:
                commodity_amount = line.sale_line_id.price_reduce_taxinc or line.product_id.list_price
                total_commodities_amount += (commodity_amount * line.quantity_done)
                commodity_description = line.product_id.name
                commodity_number_of_piece = '1'
                commodity_weight_units = self.fedex_weight_unit
                commodity_weight_value = self._fedex_convert_weight_in_ob(line.product_id.weight * line.quantity_done,
                                                                          unit=self.fedex_weight_unit)
                commodity_quantity = line.quantity_done
                commodity_quantity_units = 'EA'
                # DO NOT FORWARD PORT AFTER 12.0
                if getattr(line.product_id, 'hs_code', False):
                    commodity_harmonized_code = line.product_id.hs_code or ''
                else:
                    commodity_harmonized_code = ''
                request.commodities(_convert_curr_iso_fdx(order_currency.name), commodity_amount,
                                    commodity_number_of_piece, commodity_weight_units, commodity_weight_value,
                                    commodity_description, commodity_country_of_manufacture, commodity_quantity,
                                    commodity_quantity_units, commodity_harmonized_code)
            request.customs_value(_convert_curr_iso_fdx(order_currency.name), total_commodities_amount, "NON_DOCUMENTS")
            request.duties_payment(warehouse, shipping_account.fedex_account_number, self.fedex_duty_payment)

        # SmartPost Detail
        if self.fedex_service_type == 'SMART_POST':
            request.set_smartpost_detail(picking.smartpost_indicia, picking.smartpost_ancillary, picking.smartpost_hubId)

        # Sending Get Rate Request
        response = request.rate(return_time_in_transit=True)

        estimated_delivery_time = response.get('estimated_delivery_time', 'N/A')
        if isinstance(estimated_delivery_time, datetime.datetime):
            estimated_delivery_time = estimated_delivery_time.strftime(DEFAULT_SERVER_DATE_FORMAT)

        if response.get('errors_message'):
            return {'success': False,
                    'price': 0.0,
                    'price_without_discounts': 0.0,
                    'estimated_date': 'N/A',
                    'error_message': _('Error:\n%s') % response['errors_message'],
                    'warning_message': response.get('warnings_message')}

        price = self._fedex_convert_cost(picking.sale_id, picking.company_id, response['price'])
        price_without_discounts = self._fedex_convert_cost(picking.sale_id, picking.company_id, response['price_without_discounts'])
        return {'success': True,
                'price': price,
                'price_without_discounts': price_without_discounts,
                'estimated_date': estimated_delivery_time,
                'error_message': False,
                'warning_message': response.get('warnings_message')}

    @api.model
    def fedex_create_shipment_label(self, picking, product_packaging,
                                    package_length, package_width, package_height, weight, pickup_date,
                                    shipping_options, label_options, delivery_options, insurance_options, **kw):
        shipping_account = self.shipping_account_id
        shipper = picking.company_id.partner_id
        warehouse = picking.picking_type_id.warehouse_id.partner_id
        recipient = picking.partner_id
        residential = picking.is_residential_address

        pickup_datetime = datetime.datetime.combine(pickup_date, datetime.time(12, 0, 0))
        order_currency = picking.sale_id.currency_id or picking.company_id.currency_id
        package_type = product_packaging.shipper_package_code or 'YOUR_PACKAGING'

        advanced_options = {
            'shipping_change_billing': shipping_options['shipping_change_billing'],
            'shipping_include_return_label': label_options['shipping_include_return_label'],
            'shipping_saturday_delivery': delivery_options['shipping_saturday_delivery'],
            'shipping_cod': delivery_options['shipping_cod']
        }

        advanced_option_values = {
            'cod_payment_type': 'ANY' if picking.shipping_cod_payment_type == 'any' else 'CASH' if picking.shipping_cod_payment_type == 'cash' else 'COMPANY_CHECK',
            'cod_amount': picking.shipping_cod_amount,
        }

        # Bill to 'SENDER
        shipping_charge_payment_account = shipping_account.fedex_account_number
        shipping_charge_payment_type = 'SENDER'
        bill_duties_party = warehouse
        # Bill to 'RECIPIENT' when user chose 'Change billing'
        if advanced_options.get('shipping_change_billing'):
            shipping_charge_payment_account = picking.shipping_customer_account
            shipping_charge_payment_type = 'RECIPIENT'
            bill_duties_party = recipient

        # Configure label options
        self.fedex_label_stock_type = 'PAPER_7X4.75'
        self.fedex_label_file_type = 'PDF'

        request = FedexRequest(self.get_debug_logger_xml(picking), request_type="shipping",
                               prod_environment=shipping_account.prod_environment)

        request.web_authentication_detail(shipping_account.fedex_developer_key,
                                          shipping_account.fedex_developer_password)
        request.client_detail(shipping_account.fedex_account_number, shipping_account.fedex_meter_number)

        request.transaction_detail(picking.name)

        def _generate_shipment_request(package_type):
            request.shipment_request(dropoff_type=self.fedex_droppoff_type,
                                     service_type=self.fedex_service_type,
                                     packaging_type=package_type,
                                     overall_weight_unit=self.fedex_weight_unit,
                                     pickup_datetime=pickup_datetime)

            request.set_currency(_convert_curr_iso_fdx(order_currency.name))

            # Set special services in from "Other shipping information" tabs
            request.shipment_request_special_services(advanced_options=advanced_options,
                                                      advanced_option_values=advanced_option_values)
            request.set_pickup_detail(pickup_datetime)

            # Set insurance Amount (if user input)
            if not picking.is_mul_packages:
                request.set_insured_amount(amount=insurance_options['insurance_amount'])

            request.set_shipper(shipper, warehouse)
            request.set_recipient(recipient)
            request.set_residential(residential)

            request._shipping_charges_payment(shipping_charge_payment_account, shipping_charge_payment_type)

            request.shipment_label(label_format_type='COMMON2D',
                                   image_type=self.fedex_label_file_type,  # PDF file
                                   label_stock_type=self.fedex_label_stock_type,
                                   label_printing_orientation='TOP_EDGE_OF_TEXT_FIRST',
                                   label_order='SHIPPING_LABEL_FIRST'
                                   )

            # Commodities for customs declaration (international shipping)
            if self.fedex_service_type in ['INTERNATIONAL_ECONOMY', 'INTERNATIONAL_PRIORITY'] or (
                    recipient.country_id.code == 'IN' and warehouse.country_id.code == 'IN'):

                commodity_currency = order_currency
                total_commodities_amount = 0.0
                commodity_country_of_manufacture = warehouse.country_id.code

                for operation in picking.move_line_ids:
                    commodity_amount = operation.move_id.sale_line_id.price_reduce_taxinc or operation.product_id.list_price
                    total_commodities_amount += (commodity_amount * operation.qty_done)
                    commodity_description = operation.product_id.name
                    commodity_number_of_piece = '1'
                    commodity_weight_units = self.fedex_weight_unit
                    commodity_weight_value = self._fedex_convert_weight_in_ob(
                        operation.product_id.weight * operation.qty_done, unit=self.fedex_weight_unit)
                    commodity_quantity = operation.qty_done
                    commodity_quantity_units = 'EA'
                    # DO NOT FORWARD PORT AFTER 12.0
                    if getattr(operation.product_id, 'hs_code', False):
                        commodity_harmonized_code = operation.product_id.hs_code or ''
                    else:
                        commodity_harmonized_code = ''
                    request.commodities(_convert_curr_iso_fdx(order_currency.name), commodity_amount,
                                        commodity_number_of_piece, commodity_weight_units, commodity_weight_value,
                                        commodity_description, commodity_country_of_manufacture, commodity_quantity,
                                        commodity_quantity_units, commodity_harmonized_code)
                request.customs_value(_convert_curr_iso_fdx(commodity_currency.name), total_commodities_amount,
                                      "NON_DOCUMENTS")
                request.duties_payment(warehouse, shipping_account.fedex_account_number, self.fedex_duty_payment)
                send_etd = self.env['ir.config_parameter'].get_param("delivery_fedex.send_etd")
                request.commercial_invoice('PAPER_LETTER', send_etd)

        # For india picking courier is not accepted without this details in label.
        po_number = picking.sale_id.display_name or False
        picking_number, dept_number = picking.name, False
        if recipient.country_id.code == 'IN' and warehouse.country_id.code == 'IN':
            po_number = 'B2B' if picking.partner_id.commercial_partner_id.is_company else 'B2C'
            dept_number = 'BILL D/T: SENDER'

        if not picking.is_mul_packages:
            _generate_shipment_request(package_type)
            # Only one package
            weight_value = self._fedex_convert_weight_in_ob(weight, unit=self.fedex_weight_unit)
            # Set value for return weight
            return_weight = weight_value
            package_dimension = dict(height=package_height, width=package_width, length=package_length)
            request._add_package(
                weight_value=weight_value,
                package_code=package_type,
                service_type=self.fedex_service_type,
                package_dimension=package_dimension,
                po_number=po_number,
                dept_number=dept_number,
                reference=picking.display_name,
                picking_number=picking_number,
                confirmation=picking.fedex_shipping_confirmation,
                insurance_amount=insurance_options['insurance_amount'],
                advanced_options=advanced_options,
                advanced_option_values=advanced_option_values,
                handling_fee=picking.handling_fee
            )
            request.set_master_package(weight_value, 1)

            # SmartPost Detail
            if self.fedex_service_type == 'SMART_POST':
                request.set_smartpost_detail(picking.smartpost_indicia, picking.smartpost_ancillary, picking.smartpost_hubId)

            # Request shipment to fedEx
            response = request.process_shipment()

            # Return error message if reponse returned error
            if response.get('errors_message'):
                errors = response.get('errors_message') if isinstance(response.get('errors_message'), list) else [
                    response.get('errors_message')]
                error_message = '\n '.join(str(error) for error in errors)
                return {'success': False,
                        'price': 0.0,
                        'price_without_discounts': 0.0,
                        'estimated_date': 'N/A',
                        'tracking_number': False,
                        'error_message': _('%s\n') % error_message,
                        'warning_message': False}

            # post label attachment to picking chatter
            carrier_tracking_ref = response['tracking_number']
            log_message = (_("Shipment created into Fedex <br/> <b>Tracking Number : </b>%s") % (
                carrier_tracking_ref))
            fedex_labels = [
                ('LabelFedex-%s-%s.%s' % (carrier_tracking_ref, index, self.fedex_label_file_type), label)
                for index, label in enumerate(request._get_labels(self.fedex_label_file_type))]

            picking.message_post(body=log_message, attachments=fedex_labels)
        else:
            ################
            # Multipackage #
            ################
            # Note: Fedex has a complex multi-piece shipping interface
            # - Each package has to be sent in a separate request
            # - First package is called "master" package and holds shipping-
            #   related information, including addresses, customs...
            # - Last package responses contains shipping price and code
            # - If a problem happens with a package, every previous package
            #   of the shipping has to be cancelled separately
            master_tracking_id, package_labels, carrier_tracking_ref = False, [], ""
            package_count = len(picking.picking_package_ids)
            net_weight = self._fedex_convert_weight(sum([pkg.weight for pkg in picking.picking_package_ids]), self.fedex_weight_unit)

            for sequence, pkg in enumerate(picking.picking_package_ids, start=1):
                weight_value = self._fedex_convert_weight_in_ob(pkg.weight, unit=self.fedex_weight_unit)
                package_type = pkg.packaging_id.shipper_package_code or 'YOUR_PACKAGING'
                _generate_shipment_request(package_type)
                request._add_package(
                    weight_value=weight_value,
                    package_code=package_type,
                    service_type=self.fedex_service_type,
                    package_dimension=dict(width=pkg.width, height=pkg.height, length=pkg.length),
                    po_number=po_number,
                    dept_number=dept_number,
                    picking_number=picking_number,
                    sequence_number=sequence,
                    reference=picking.display_name,
                    confirmation=picking.fedex_shipping_confirmation,
                    advanced_options=advanced_options,
                    advanced_option_values=advanced_option_values,
                    handling_fee=pkg.handling_fee
                )
                request.set_master_package(net_weight, package_count, master_tracking_id=master_tracking_id)
                response = request.process_shipment()

                # Return error message if reponse returned error
                if response.get('errors_message'):
                    # If there is any package created before then we should void the first package
                    # Which holds the master tracking id
                    if master_tracking_id:
                        self.fedex_void_label(picking, master_tracking_id)
                        # Remove all carrier_tracking_ref in each package
                        picking.picking_package_ids.write(dict(carrier_tracking_ref=False))

                    errors = response.get('errors_message') if isinstance(response.get('errors_message'), list) else [response.get('errors_message')]
                    error_message = ('Error when sending package No. %s \n ' % sequence).join(str(error) for error in errors)
                    return {'success': False,
                            'price': 0.0,
                            'price_without_discounts': 0.0,
                            'estimated_date': 'N/A',
                            'tracking_number': False,
                            'error_message': _('%s\n') % error_message,
                            'warning_message': False}

                package_name = sequence
                package_labels.append((package_name, request.get_label()))
                # First package
                if sequence == 1:
                    # Set value for return label
                    package_dimension = dict(width=pkg.width, height=pkg.height, length=pkg.length)
                    return_weight = pkg.weight
                    master_tracking_id = response['master_tracking_id']
                    carrier_tracking_ref = response['tracking_number']

                # Intermediary packages
                # elif sequence > 1 and sequence < package_count:
                    # Concat carrier tracking ref with previous one
                    # carrier_tracking_ref += "," + response['tracking_number']

                # Last package
                elif sequence == package_count:
                    # Concat carrier tracking ref with previous one
                    # carrier_tracking_ref += "," + response['tracking_number']

                    log_message = _("Shipment created into Fedex<br/>"
                                   "<b>Tracking Numbers:</b> %s<br/>"
                                   "<b>Packages:</b> %s") % (
                                 carrier_tracking_ref, ', '.join([str(pl[0]) for pl in package_labels]))
                    if self.fedex_label_file_type != 'PDF':
                        attachments = [('LabelFedex-%s.%s' % (str(pl[0]), self.fedex_label_file_type), pl[1]) for pl in
                                       package_labels]
                    if self.fedex_label_file_type == 'PDF':
                        attachments = [('LabelFedex-%s.pdf' % str(carrier_tracking_ref), pdf.merge_pdf([pl[1] for pl in package_labels]))]
                    picking.message_post(body=log_message, attachments=attachments)
                # Write carrier tracking referrence for each package
                pkg.write(dict(carrier_tracking_ref=response['tracking_number']))

        commercial_invoice = request.get_document()
        if commercial_invoice:
            fedex_documents = [('DocumentFedex.pdf', commercial_invoice)]
            picking.message_post(body=_('Fedex Documents'), attachments=fedex_documents)

        # Get shipping price and cost
        price = self._fedex_convert_cost(picking.sale_id, picking.company_id, response['price'])
        price_without_discounts = self._fedex_convert_cost(picking.sale_id, picking.company_id,
                                                           response['price_without_discounts'])
        insurance_cost = self._fedex_convert_cost(picking.sale_id, picking.company_id,
                                                  response['insurance']) if response.get('insurance') else False
        # Format delivery time to server format
        delivery_time = response.get('date', 'N/A')
        # Create return label if user chose "include return label option"
        if advanced_options.get('shipping_include_return_label'):
            tracking_number = carrier_tracking_ref.split(',')[0]
            self.omni_fedex_get_return_label(picking=picking, product_packaging=product_packaging,
                                             package_dimension=package_dimension, weight=return_weight,
                                             pickup_datetime=pickup_datetime, advanced_options=advanced_options,
                                             tracking_number=tracking_number, origin_date=delivery_time)

        if isinstance(delivery_time, datetime.date):
            delivery_time = str(delivery_time.strftime(DEFAULT_SERVER_DATE_FORMAT))

        return {
            'success': True,
            'price': price,
            'price_without_discounts': price_without_discounts,
            'insurance_cost': insurance_cost,
            'estimated_date': delivery_time,
            'carrier_tracking_ref': carrier_tracking_ref,
            'error_message': False,
            'warning_message': False
        }

    def omni_fedex_get_return_label(self, picking, product_packaging, package_dimension, weight, pickup_datetime,
                                    advanced_options={}, tracking_number=None, origin_date=None):
        shipping_account = self.shipping_account_id
        package_type = product_packaging.shipper_package_code or 'YOUR_PACKAGING'

        warehouse = picking.picking_type_id.warehouse_id.partner_id
        recipient = picking.company_id.partner_id
        shipper = picking.partner_id

        order_currency = picking.sale_id.currency_id or picking.company_id.currency_id

        request = FedexRequest(self.get_debug_logger_xml(None), request_type="shipping",
                               prod_environment=shipping_account.prod_environment)

        request.web_authentication_detail(shipping_account.fedex_developer_key,
                                          shipping_account.fedex_developer_password)
        request.client_detail(shipping_account.fedex_account_number, shipping_account.fedex_meter_number)

        request.transaction_detail(picking.name)

        request.shipment_request(dropoff_type=self.fedex_droppoff_type,
                                 service_type=self.fedex_service_type,
                                 packaging_type=package_type,
                                 overall_weight_unit=self.fedex_weight_unit,
                                 pickup_datetime=pickup_datetime)

        request.set_currency(_convert_curr_iso_fdx(order_currency.name))

        request.set_shipper(shipper, warehouse)
        request.set_recipient(recipient)

        shipping_charge_payment_account = shipping_account.fedex_account_number
        shipping_charge_payment_type = 'SENDER'
        bill_duties_party = warehouse
        if advanced_options.get('shipping_change_billing'):
            shipping_charge_payment_account = picking.shipping_customer_account
            shipping_charge_payment_type = 'RECIPIENT'
            bill_duties_party = recipient
        request._shipping_charges_payment(shipping_charge_payment_account, shipping_charge_payment_type)

        request.shipment_label(label_format_type='COMMON2D',
                               image_type=self.fedex_label_file_type,
                               label_stock_type=self.fedex_label_stock_type,
                               label_printing_orientation='TOP_EDGE_OF_TEXT_FIRST',
                               label_order='SHIPPING_LABEL_FIRST',
                               )

        net_weight = self._fedex_convert_weight_in_ob(weight, unit=self.fedex_weight_unit)
        po_number = picking.sale_id.display_name or False
        picking_number, dept_number = picking.name, False

        request._add_package(
            weight_value=net_weight,
            package_code=package_type,
            package_dimension=package_dimension,
            reference=picking.display_name,
            po_number=po_number,
            dept_number=dept_number,
            picking_number=picking_number
        )

        request.set_master_package(net_weight, 1)
        if self.fedex_service_type in ['INTERNATIONAL_ECONOMY', 'INTERNATIONAL_PRIORITY'] or (
                recipient.country_id.code == 'IN' and warehouse.country_id.code == 'IN'):

            commodity_currency = order_currency
            total_commodities_amount = 0.0
            commodity_country_of_manufacture = picking.picking_type_id.warehouse_id.partner_id.country_id.code

            for operation in picking.move_line_ids:
                commodity_amount = operation.move_id.sale_line_id.price_unit or operation.product_id.list_price
                total_commodities_amount += (commodity_amount * operation.qty_done)
                commodity_description = operation.product_id.name
                commodity_number_of_piece = '1'
                commodity_weight_units = self.fedex_weight_unit
                if operation.state == 'done':
                    commodity_weight_value = self._fedex_convert_weight(
                        operation.product_id.weight * operation.qty_done, self.fedex_weight_unit)
                    commodity_quantity = operation.qty_done
                else:
                    commodity_weight_value = self._fedex_convert_weight(
                        operation.product_id.weight * operation.product_uom_qty, self.fedex_weight_unit)
                    commodity_quantity = operation.product_uom_qty
                commodity_quantity_units = 'EA'
                commodity_harmonized_code = operation.product_id.hs_code or ''
                request.commodities(_convert_curr_iso_fdx(commodity_currency.name), commodity_amount,
                                    commodity_number_of_piece, commodity_weight_units, commodity_weight_value,
                                    commodity_description, commodity_country_of_manufacture, commodity_quantity,
                                    commodity_quantity_units, commodity_harmonized_code)
            request.customs_value(_convert_curr_iso_fdx(commodity_currency.name), total_commodities_amount,
                                  "NON_DOCUMENTS")
            # We consider that returns are always paid by the company creating the label

            request.duties_payment(warehouse, shipping_account.fedex_account_number, 'SENDER')

        request.return_label(tracking_number, origin_date)

        response = request.process_shipment()

        if not response.get('errors_message'):
            # company_currency = picking.company_id.currency_id
            # price = self._fedex_convert_cost(picking.sale_id, picking.company_id, response['price'])
            #
            # insurance_cost = self._fedex_convert_cost(picking.sale_id, picking.company_id, response['insurance']) if response.get('insurance') else 0

            fedex_labels = [('%s-%s-%s.%s' % (
                self.get_return_label_prefix(), response['tracking_number'], index, self.fedex_label_file_type), label)
                            for index, label in enumerate(request._get_labels(self.fedex_label_file_type))]

            picking.message_post(body=_('Return Label'), attachments=fedex_labels)

            # return {'success': True,
            #         'return_price': price,
            #         'return_insurance_cost': insurance_cost}
        else:
            title = 'Cannot create return label !'
            exceptions = [{'title': 'Message from fedEx',
                           'reason': response['errors_message']}]
            picking._log_exceptions_on_picking(title, exceptions)

    @api.model
    def fedex_void_label(self, picking, master_tracking_id=False):
        request = FedexRequest(self.get_debug_logger_xml(picking), request_type="shipping",
                               prod_environment=self.prod_environment)
        shipping_account = self.shipping_account_id
        request.web_authentication_detail(shipping_account.fedex_developer_key,
                                          shipping_account.fedex_developer_password)
        request.client_detail(shipping_account.fedex_account_number, shipping_account.fedex_meter_number)
        request.transaction_detail(picking.id)

        if not master_tracking_id:
            master_tracking_id = picking.carrier_tracking_ref.split(',')[0] if picking.carrier_tracking_ref else False

        request.set_deletion_details(master_tracking_id)
        result = request.delete_shipment()

        if result.get('delete_success') and not result.get('errors_message'):
            picking.message_post(body=_(u'Shipment N° %s has been cancelled') % picking.carrier_tracking_ref)

            return {
                'success': True,
                'error_message': False,
                'warning_message': _('Warning: %s') % result.get('warnings_message', False)}
        else:
            return {
                'success': False,
                'error_message': _('Error: %s') % result.get('errors_message', False),
                'warning_message': _('Warning: %s') % result.get('warnings_message', False)}
