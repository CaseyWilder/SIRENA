# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from odoo import api, models, fields, _, tools
from odoo.addons.delivery_fedex.models.delivery_fedex import _convert_curr_iso_fdx

from odoo.addons.omni_fedex.models.fedex_request import FedexRequest

import logging

_logger = logging.getLogger(__name__)


class ProviderFedex(models.Model):
    _inherit = 'delivery.carrier'

    def omni_fedex_get_return_label(self, picking, product_packaging, package_dimension, weight, pickup_datetime,
                                    advanced_options={}, tracking_number=None, origin_date=None):
        # [SRN-94] FedEx Ground for all return labels
        original_shipping_service = self.fedex_service_type
        self.fedex_service_type = 'FEDEX_GROUND'
        # [SRN-94]

        shipping_account = self.shipping_account_id
        package_type = product_packaging.shipper_package_code or 'YOUR_PACKAGING'

        warehouse = picking.picking_type_id.warehouse_id.partner_id
        recipient = picking.company_id.partner_id
        shipper = picking.partner_id
        residential_shipper = picking.is_residential_address

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

        request.set_shipper(shipper, shipper)
        request.set_recipient(recipient)
        request.set_residential_recipient(False)
        request.set_residential_shipper(residential_shipper)

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

        if advanced_options.get('shipping_include_return_label'):
            request.shipment_request_special_services(advanced_options={}, advanced_option_values={})

        if self.fedex_service_type == 'SMART_POST':
            request.set_smartpost_detail('PARCEL_RETURN', 'NONE', picking.smartpost_hubId)

        request.return_label(tracking_number, origin_date)

        # [SRN-94] FedEx Ground for all return labels
        self.fedex_service_type = original_shipping_service
        # [SRN-94]

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
            return {'errors_message': False}

            # return {'success': True,
            #         'return_price': price,
            #         'return_insurance_cost': insurance_cost}
        else:
            title = 'Cannot create return label !'
            exceptions = [{'title': 'Message from fedEx',
                           'reason': response['errors_message']}]
            #picking._log_exceptions_on_picking(title, exceptions)
            _logger.error(response['errors_message'])
            return {'errors_message': response['errors_message']}
