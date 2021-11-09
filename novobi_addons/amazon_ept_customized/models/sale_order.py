from odoo import models, fields, api, _


class SaleOrder(models.Model):
    _inherit = "sale.order"

    @staticmethod
    def amz_get_carrier_name_ept(picking):
        carrier_dict = {}
        if picking.delivery_carrier_id and picking.delivery_carrier_id.amz_carrier_code:
            if picking.delivery_carrier_id.amz_carrier_code == 'Other':
                carrier_dict.update({'carrier_code': picking.delivery_carrier_id.amz_carrier_code,
                                     'carrier_name': picking.delivery_carrier_id.name})
            else:
                carrier_dict.update({'carrier_code': picking.delivery_carrier_id.amz_carrier_code})
        else:
            carrier_dict.update({'carrier_code': 'Other', 'carrier_name': picking.delivery_carrier_id.name})
        return carrier_dict

    @staticmethod
    def amz_prepare_parcel_values_ept(carrier_name, tracking_no, amazon_order, fulfillment_date_concat):

        delivery_carrier_ids = amazon_order.picking_ids.mapped('delivery_carrier_id')
        fbm_shipping_methods = delivery_carrier_ids.mapped('fbm_shipping_method')
        amz_shipping_service_level_categories = delivery_carrier_ids.mapped('amz_shipping_service_level_category')
        shipment_service_level_category = fbm_shipping_methods and fbm_shipping_methods[0] \
                                          or amz_shipping_service_level_categories and amz_shipping_service_level_categories[0] \
                                          or amazon_order.amz_shipment_service_level_category
        parcel = {
            'tracking_no': tracking_no or '',
            'order_ref': amazon_order.amz_order_reference,
            'shipping_level_category': shipment_service_level_category,
            'fulfillment_date_concat': fulfillment_date_concat or False
        }
        if carrier_name:
            parcel.update(carrier_name)

        return parcel

    @staticmethod
    def create_parcel_for_single_tracking_number(parcel, message_id, ship_info):
        message_information = ''
        if parcel.get('carrier_code'):
            carrier_information = '''<CarrierCode>%s</CarrierCode>''' % (parcel.get('carrier_code'))
            if parcel.get('carrier_name', False):
                carrier_information += '''<CarrierName>%s</CarrierName>''' % (parcel.get('carrier_name'))
        else:
            carrier_information = '''<CarrierName>%s</CarrierName>''' % (parcel.get('carrier_name'))
        message_information += """<Message>
                                        <MessageID>%s</MessageID>
                                        <OperationType>Update</OperationType>
                                        <OrderFulfillment>
                                            <AmazonOrderID>%s</AmazonOrderID>
                                            <FulfillmentDate>%s</FulfillmentDate>
                                            <FulfillmentData>
                                                %s
                                                <ShippingMethod>%s</ShippingMethod>
                                                <ShipperTrackingNumber>%s</ShipperTrackingNumber>
                                            </FulfillmentData>
                                            %s
                                        </OrderFulfillment>
                                    </Message>""" % (
            str(message_id), parcel.get('order_ref'), parcel.get('fulfillment_date_concat'),
            carrier_information, parcel.get('shipping_level_category'), parcel.get('tracking_no'), ship_info)
        return message_information

    def create_parcel_for_multi_tracking_number(self, parcel, message_id, order):
        message_information = ''
        ship_info = ""
        partner = order.warehouse_id.partner_id
        if partner:
            ship_info = self.amz_get_ship_from_address_details(partner)
        if parcel.get('carrier_code'):
            carrier_information = '''<CarrierCode>%s</CarrierCode>''' % (parcel.get('carrier_code'))
            if parcel.get('carrier_name', False):
                carrier_information += '''<CarrierName>%s</CarrierName>''' % (parcel.get('carrier_name'))
        else:
            carrier_information = '''<CarrierName>%s</CarrierName>''' % (parcel.get('carrier_name'))
        item_string = '''<Item>
                                <AmazonOrderItemCode>%s</AmazonOrderItemCode>
                                <Quantity>%s</Quantity>
                          </Item>''' % (parcel.get('amazon_order_item_id'), parcel.get('qty', 0))
        message_information += """<Message>
                                        <MessageID>%s</MessageID>
                                        <OperationType>Update</OperationType>
                                        <OrderFulfillment>
                                            <AmazonOrderID>%s</AmazonOrderID>
                                            <FulfillmentDate>%s</FulfillmentDate>
                                            <FulfillmentData>
                                                %s
                                                <ShippingMethod>%s</ShippingMethod>
                                                <ShipperTrackingNumber>%s</ShipperTrackingNumber>
                                            </FulfillmentData>
                                            %s
                                            %s
                                        </OrderFulfillment>
                                    </Message>""" % (
            str(message_id), parcel.get('order_ref'), parcel.get('fulfillment_date_concat'),
            carrier_information, parcel.get('shipping_level_category'), parcel.get('tracking_no'), item_string, ship_info)
        return message_information