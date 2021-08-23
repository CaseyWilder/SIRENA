# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

"""
Inherited sale order and fields to create amazon sale orders in odoo.
"""

import json
import logging
import time
from datetime import datetime, timedelta

import pytz
from dateutil import parser
from odoo import models, fields, api, _
from odoo.addons.iap.tools import iap_tools
from odoo.exceptions import UserError

from ..endpoint import DEFAULT_ENDPOINT

utc = pytz.utc
_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    """
    inherited class to create amazon sales order in odoo.
    """
    _inherit = "sale.order"

    def _search_order_ids_amazon(self, operator, value):
        # inner join amazon_sale_order_ept on sale_order_id=sale_order.id
        query = """
                select sale_order.id from stock_picking           
                inner join sale_order on sale_order.procurement_group_id=stock_picking.group_id
                inner join stock_location on stock_location.id=stock_picking.location_dest_id and 
                stock_location.usage='customer'                
                where stock_picking.updated_in_amazon=False and stock_picking.state='done'    
              """
        self._cr.execute(query)
        results = self._cr.fetchall()
        order_ids = []
        for result_tuple in results:
            order_ids.append(result_tuple[0])
        return [('id', 'in', order_ids)]

    def _compute_amazon_status(self):
        """
        This will get amazon status and update in order.
        """
        for order in self:
            if order.picking_ids:
                order.updated_in_amazon = True
            else:
                order.updated_in_amazon = False
            for picking in order.picking_ids:
                if picking.state == 'cancel':
                    continue
                if picking.location_dest_id.usage != 'customer':
                    continue
                if not picking.updated_in_amazon:
                    order.updated_in_amazon = False
                    break

    @api.onchange('warehouse_id')
    def _compute_is_fba_warehouse(self):
        """
        This method will check is order has FBA warehouse.
        """
        for record in self:
            if record.warehouse_id.is_fba_warehouse:
                record.order_has_fba_warehouse = True
            else:
                record.order_has_fba_warehouse = False

    full_fill_ment_order_help = """
            RECEIVED:The fulfillment order was received by Amazon Marketplace Web Service (Amazon 
            MWS) 
                     and validated. Validation includes determining that the destination address is 
                     valid and that Amazon's records indicate that the seller has enough sellable 
                     (undamaged) inventory to fulfill the order. The seller can cancel a 
                     fulfillment 
                     order that has a status of RECEIVED
            INVALID:The fulfillment order was received by Amazon Marketplace Web Service (Amazon 
            MWS) 
                    but could not be validated. The reasons for this include an invalid destination 
                    address or Amazon's records indicating that the seller does not have enough 
                    sellable 
                    inventory to fulfill the order. When this happens, the fulfillment order is 
                    invalid 
                    and no items in the order will ship
            PLANNING:The fulfillment order has been sent to the Amazon Fulfillment Network to begin 
                     shipment planning, but no unit in any shipment has been picked from 
                     inventory yet. 
                     The seller can cancel a fulfillment order that has a status of PLANNING
            PROCESSING:The process of picking units from inventory has begun on at least one 
            shipment 
                       in the fulfillment order. The seller cannot cancel a fulfillment order that 
                       has a status of PROCESSING
            CANCELLED:The fulfillment order has been cancelled by the seller.
            COMPLETE:All item quantities in the fulfillment order have been fulfilled.
            COMPLETE_PARTIALLED:Some item quantities in the fulfillment order were fulfilled; the 
            rest were either cancelled or unfulfillable.
            UNFULFILLABLE: item quantities in the fulfillment order could be fulfilled because t
            he Amazon fulfillment center workers found no inventory 
            for those items or found no inventory that was in sellable (undamaged) condition.
        """

    help_fulfillment_action = """
            Ship - The fulfillment order ships now

            Hold - An order hold is put on the fulfillment order.

            Default: Ship in Create Fulfillment
            Default: Hold in Update Fulfillment    
        """

    help_fulfillment_policy = """
            FillOrKill - If an item in a fulfillment order is determined to be unfulfillable 
            before any 
                        shipment in the order moves to the Pending status (the process of picking 
                        units 
                        from inventory has begun), then the entire order is considered 
                        unfulfillable. 
                        However, if an item in a fulfillment order is determined to be 
                        unfulfillable 
                        after a shipment in the order moves to the Pending status, Amazon cancels 
                        as 
                        much of the fulfillment order as possible

            FillAll - All fulfillable items in the fulfillment order are shipped. 
                    The fulfillment order remains in a processing state until all items are either 
                    shipped by Amazon or cancelled by the seller

            FillAllAvailable - All fulfillable items in the fulfillment order are shipped. 
                All unfulfillable items in the order are cancelled by Amazon.

            Default: FillOrKill
        """

    amz_instance_id = fields.Many2one('amazon.instance.ept', string='Amazon Instance',
                                      help="Amazon Instance")
    amz_seller_id = fields.Many2one('amazon.seller.ept', string='Amazon Seller',
                                    help="Unique Amazon Seller name")
    amz_fulfillment_by = fields.Selection(
        [('FBA', 'Amazon Fulfillment Network'), ('FBM', 'Merchant Fullfillment Network')],
        string="Fulfillment By", help="Fulfillment Center by Amazon or Merchant")
    amz_order_reference = fields.Char('Amazon Order Reference', help="Amazon Order Reference")
    is_business_order = fields.Boolean('Business Order', default=False,
                                       help="True, if Business order")
    is_prime_order = fields.Boolean('Amazon Prime Order', default=False,
                                    help="True, if Prime order")
    amz_shipment_service_level_category = fields.Selection(
        [('Expedited', 'Expedited'), ('NextDay', 'NextDay'), ('SecondDay', 'SecondDay'),
         ('Standard', 'Standard'), ('FreeEconomy', 'FreeEconomy'), ('Priority', 'Priority'),
         ('ScheduledDelivery', 'ScheduledDelivery'), ('SameDay','SameDay'), ('Scheduled', 'Scheduled')],
        string="FBA Shipping Speed", default='Standard', help="ScheduledDelivery used only for japan")
    is_fba_pending_order = fields.Boolean("Is FBA Pending Order?", default=False,
                                          help="To Identify order is pending order or not")
    amz_shipment_report_id = fields.Many2one('shipping.report.request.history',
                                             string="Amazon Shipping Report",
                                             help="To identify Shipment report")
    seller_id = fields.Many2one('amazon.seller.ept', string="Seller Name", help="Amazon Seller Id")
    amz_sales_order_report_id = fields.Many2one('fbm.sale.order.report.ept',
                                                string="Sales Order Report Id")
    updated_in_amazon = fields.Boolean(compute="_compute_amazon_status",
                                       search='_search_order_ids_amazon', store=False)
    amz_is_outbound_order = fields.Boolean("Out Bound Order", default=False,
                                           help="If true Outbound order is created")
    order_has_fba_warehouse = fields.Boolean("Order Has FBA Warehouse",
                                             compute="_compute_is_fba_warehouse", store=False,
                                             help="True, If warehouse is set as FBA Warehouse")
    amz_fulfillment_action = fields.Selection([('Ship', 'Ship'), ('Hold', 'Hold')],
                                              string="Fulfillment Action", default="Hold",
                                              help=help_fulfillment_action)
    amz_fulfillment_policy = fields.Selection([('FillOrKill', 'FillOrKill'), ('FillAll', 'FillAll'),
                                               ('FillAllAvailable', 'FillAllAvailable')],
                                              string="Fulfillment Policy", default="FillOrKill",
                                              required=False, help=help_fulfillment_policy)
    amz_fulfullment_order_status = fields.Selection(
        [('RECEIVED', 'RECEIVED'), ('INVALID', 'INVALID'), ('PLANNING', 'PLANNING'),
         ('PROCESSING', 'PROCESSING'), ('CANCELLED', 'CANCELLED'), ('COMPLETE', 'COMPLETE'),
         ('COMPLETE_PARTIALLED', 'COMPLETE_PARTIALLED'), ('UNFULFILLABLE', 'UNFULFILLABLE')],
        string="Fulfillment Order Status", help=full_fill_ment_order_help)
    exported_in_amazon = fields.Boolean(default=False)
    amz_displayable_date_time = fields.Date("Displayable Order Date Time", required=False,
                                            help="Display Date in package")
    notify_by_email = fields.Boolean(default=False,
                                     help="If true then system will notify by email to followers")
    amz_delivery_start_time = fields.Datetime("Delivery Start Time",
                                              help="Delivery Estimated Start Time")
    amz_delivery_end_time = fields.Datetime("Delivery End Time", help="Delivery Estimated End Time")
    is_amazon_canceled = fields.Boolean("Canceled In amazon ?", default=False)
    amz_fulfillment_instance_id = fields.Many2one('amazon.instance.ept',
                                                  string="Fulfillment Instance")
    amz_instance_country_code = fields.Char(related="amz_instance_id.country_id.code",
                                            readonly=True,
                                            string="Marketplace Country",
                                            help="Used for display line_tax_amount in order line for US country")

    _sql_constraints = [('amazon_sale_order_unique_constraint',
                         'unique(amz_instance_id, amz_order_reference, warehouse_id, '
                         'amz_fulfillment_by)',
                         "Amazon sale order must be unique.")]

    @api.constrains('amz_fulfillment_action')
    def check_fulfillment_action(self):
        """
        Added constraint for which sale order is already exported to amazon but action not updated.
        """
        for record in self:
            if record.sudo().exported_in_amazon and record.sudo().amz_fulfillment_action == 'Hold':
                raise UserError(_(
                    "You can change action Ship to Hold Which are already exported in amazon"))

    def _prepare_procurement_group_vals(self):

        """
        This Function used to add seller_id to picking for the FBM Orders.
        @author: Keyur Kanani
        :return:
        """
        res = super(SaleOrder, self)._prepare_procurement_group_vals()
        if self.amz_seller_id:
            res.update({'seller_id': self.amz_seller_id.id})
        return res

    def _prepare_invoice(self):
        """
        Add amazon_instance_id and fulfillment_by When invoice create
        @author: Keyur Kanani
        :return:
        """
        res = super(SaleOrder, self)._prepare_invoice()
        if self.amz_instance_id:
            res.update(({'amazon_instance_id': self.amz_instance_id and
                                               self.amz_instance_id.id or False,
                         'amz_fulfillment_by': self.amz_fulfillment_by or False,
                         'amz_sale_order_id': self.id or False
                         }))
        return res

    def get_data(self):
        """
        This method will prepare dict for outbound orders.
        """
        data = {}
        data.update({
            'SellerFulfillmentOrderId': self.name,
            'DisplayableOrderId': self.amz_order_reference,
            'ShippingSpeedCategory': self.amz_shipment_service_level_category,
        })
        if self.amz_delivery_start_time and self.amz_delivery_end_time:
            start_date = self.amz_delivery_start_time.strftime("%Y-%m-%dT%H:%M:%S")
            start_date = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(
                time.mktime(time.strptime(start_date, "%Y-%m-%dT%H:%M:%S"))))
            start_date = str(start_date) + 'Z'

            end_date = self.amz_delivery_end_time.strftime("%Y-%m-%dT%H:%M:%S")
            end_date = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(
                time.mktime(time.strptime(end_date, "%Y-%m-%dT%H:%M:%S"))))
            end_date = str(end_date) + 'Z'
            data.update({
                'DeliveryWindow.StartDateTime': start_date,
                'DeliveryWindow.EndDateTime': end_date,
            })

        data.update({
            'DestinationAddress.Name': str(self.partner_shipping_id.name),
            'DestinationAddress.Line1': str(self.partner_shipping_id.street or ''),
            'DestinationAddress.Line2': str(self.partner_shipping_id.street2 or ''),
            'DestinationAddress.CountryCode': str(self.partner_shipping_id.country_id.code or ''),
            'DestinationAddress.City': str(self.partner_shipping_id.city or ''),
            'DestinationAddress.StateOrProvinceCode': str(self.partner_shipping_id.state_id and
                                                          self.partner_shipping_id.state_id.code
                                                          or ''),
            'DestinationAddress.PostalCode': str(self.partner_shipping_id.zip or ''),
        })
        if self.note:
            data.update({'DisplayableOrderComment': str(self.note)})
        data.update({
            'DisplayableOrderDateTime': str(self.amz_displayable_date_time.strftime('%Y-%m-%d')),
            'FulfillmentAction': str(self.amz_fulfillment_action),

        })
        count = 1
        for line in self.order_line:
            if line.product_id and line.product_id.type == 'service':
                continue

            key = "Items.member.%s.Quantity" % (count)
            data.update({key: str(int(line.product_uom_qty))})
            key = "Items.member.%s.SellerSKU" % (count)
            data.update({key: str(line.amazon_product_id.seller_sku)})
            key = "Items.member.%s.SellerFulfillmentOrderItemId" % (count)
            data.update({key: str(line.amazon_product_id.seller_sku)})
            count = count + 1
        if self.notify_by_email:
            count = 1
            for follower in self.message_follower_ids:
                if follower.partner_id.email:
                    key = "NotificationEmailList.member.%s" % (count)
                    data.update({key: str(follower.partner_id.email)})
                    count = count + 1
        return data

    def import_fba_pending_sales_order(self, seller, marketplaceids, updated_after_date):
        """
        Create Object for the integrate with amazon
        Import FBA Pending Sales Order From Amazon
        :param seller: amazon.seller.ept()
        :param marketplaceids: list of Marketplaces
        :return:
        """
        """If Last FBA Sync Time is define then system will take those orders which are created
        after last import time Otherwise System will take last 30 days orders
        """
        if not marketplaceids:
            marketplaceids = tuple([x.market_place_id for x in seller.instance_ids])
        if not marketplaceids:
            raise UserError(
                _("There is no any instance is configured of seller %s" % (seller.name)))

        if updated_after_date:
            updated_after = updated_after_date.strftime("%Y-%m-%d %H:%M:%S")
            db_import_time = time.strptime(str(updated_after), "%Y-%m-%d %H:%M:%S")
            db_import_time = time.strftime("%Y-%m-%dT%H:%M:%S", db_import_time)
            updated_after_date = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(
                time.mktime(time.strptime(db_import_time, "%Y-%m-%dT%H:%M:%S"))))
            updated_after_date = str(updated_after_date) + 'Z'
            seller.fba_pending_order_last_sync_on = updated_after
        elif seller.fba_pending_order_last_sync_on:
            earlier = seller.fba_pending_order_last_sync_on - timedelta(days=3)
            earlier_str = earlier.strftime("%Y-%m-%dT%H:%M:%S")
            updated_after_date = earlier_str + 'Z'
            seller.fba_pending_order_last_sync_on = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        else:
            earlier = datetime.now() - timedelta(days=30)
            updated_after_date = earlier.strftime("%Y-%m-%dT%H:%M:%S") + 'Z'
            seller.fba_pending_order_last_sync_on = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        kwargs = self.prepare_amazon_request_report_kwargs(seller,
                                                           'import_fba_pending_sales_order_v13')
        kwargs.update({'updated_after': updated_after_date,
                       'marketplaceids': marketplaceids, })

        response = iap_tools.iap_jsonrpc(DEFAULT_ENDPOINT + '/iap_request', params=kwargs, timeout=1000)
        if response.get('reason'):
            raise UserError(_(response.get('reason')))

        result = response.get('result')
        self.process_fba_pending_sale_order_response(seller, kwargs, result)
        return True

    def process_fba_pending_sale_order_response(self, seller, kwargs, result):
        """
        This method is used to process fba pending sale order response to create pending sale
        order.
        """
        self.create_amazon_pending_sales_order(seller, [result])
        self._cr.commit()
        next_token = result.get('NextToken', {}).get('value')

        """We have create list of Dictwrapper now we create orders into system"""
        kwargs.update({'next_token': next_token,
                       'emipro_api': 'order_by_next_token_v13', })

        response = iap_tools.iap_jsonrpc(DEFAULT_ENDPOINT + '/iap_request', params=kwargs, timeout=1000)
        if response.get('reason'):
            raise UserError(_(response.get('reason')))

        order_by_next_token = response.get('result')
        for result in order_by_next_token:
            self.create_amazon_pending_sales_order(seller, [result])
            self._cr.commit()
        return True

    def cancel_amazon_fba_pending_sale_orders(self, seller, marketplaceids, instance_ids):
        """
        Check Status of draft order in Amazon and if it is cancel, then cancel that order in Odoo
        Create Object for the integrate with amazon
        :param seller: amazon.seller.ept()
        :param marketplaceids: list[]
        :param instance_ids: list[]
        :return:
        """

        auto_process = self._context.get('auto_process', False)
        domain = [('state', '=', 'draft'), ('amz_fulfillment_by', '=', 'FBA')]

        if instance_ids:
            domain.append(('amz_instance_id', 'in', instance_ids))

        min_draft_order = self.search(domain, limit=1, order='date_order')
        max_draft_order = self.search(domain, limit=1, order='date_order desc')
        if not min_draft_order or not max_draft_order:
            if not auto_process:
                raise UserError(_("No draft order found in odoo"))
            return []

        if not marketplaceids:
            marketplaceids = tuple([x.market_place_id for x in seller.instance_ids])
            if not marketplaceids:
                if not auto_process:
                    raise UserError(_( \
                        "There is no any instance is configured of seller %s" % (seller.name)))
                return []

        min_date = datetime.strptime(str(min_draft_order.date_order), "%Y-%m-%d %H:%M:%S")
        max_date = datetime.strptime(str(max_draft_order.date_order), "%Y-%m-%d %H:%M:%S")
        date_ranges = {}
        date_from = min_date
        while date_from < max_date or date_from < datetime.now():
            date_to = date_from + timedelta(days=30)
            if date_to > max_date:
                date_to = max_date
            if date_to > datetime.now():
                date_to = datetime.now()
            date_ranges.update({date_from: date_to})
            date_from = date_from + timedelta(days=31)

        for from_date, to_date in list(date_ranges.items()):
            min_date_str = from_date.strftime("%Y-%m-%dT%H:%M:%S")
            created_after = min_date_str + 'Z'

            list_of_wrapper = self.check_amazon_fba_and_fbm_cancel_order(seller, marketplaceids,
                                                                         created_after, 'AFN')

            for result in list_of_wrapper:
                self.with_context( \
                    {'fulfillment_by': 'FBA'}).cancel_amazon_draft_sales_order(seller, [result])
                self._cr.commit()
        return True

    def cancel_amazon_fbm_pending_sale_orders(self, seller, marketplaceids, instance_ids):
        """
        Check Status of draft order in Amazon and if it is cancel, then cancel that order in Odoo
        Create Object for the integrate with amazon
        :param seller: amazon.seller.ept()
        :return:
        """
        auto_process = self._context.get('is_auto_process', False)

        orders = self.search(
            [('amz_seller_id', '=', seller.id), ('amz_fulfillment_by', '=', 'FBM'),
             ('amz_instance_id', 'in', instance_ids)],
            order='date_order asc')

        unshipped_orders = orders.filtered(lambda order: order.mapped('picking_ids').filtered( \
            lambda
                pick: pick.state == 'confirmed' and pick.picking_type_code == 'outgoing')).sorted( \
            key=lambda order: order.date_order)
        if unshipped_orders:
            updated_after_date = unshipped_orders[0].date_order - timedelta(+1)
            if not marketplaceids:
                marketplaceids = tuple([x.market_place_id for x in seller.instance_ids])
                if not marketplaceids:
                    if not auto_process:
                        raise UserError(_( \
                            "There is no any instance is configured of seller %s" % (seller.name)))
                    return []

            if updated_after_date:
                db_import_time = time.strptime(str(updated_after_date), "%Y-%m-%d %H:%M:%S")
                db_import_time = time.strftime("%Y-%m-%dT%H:%M:%S", db_import_time)
                start_date = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(
                    time.mktime(time.strptime(db_import_time, "%Y-%m-%dT%H:%M:%S"))))
                updated_after_date = str(start_date) + 'Z'

            list_of_wrapper = self.check_amazon_fba_and_fbm_cancel_order(seller, marketplaceids, \
                                                                         updated_after_date, 'MFN')
            for result in list_of_wrapper:
                self.with_context({'fulfillment_by': 'FBM'}).cancel_amazon_draft_sales_order(seller,
                                                                                             [
                                                                                                 result])
                self._cr.commit()
        return True

    def check_amazon_fba_and_fbm_cancel_order(self, seller, marketplaceids, updated_after,
                                              fulfillment_channels):
        """
        This method will request for check cancel order in amazon and return the response
        :param seller : seller record
        :param marketplaces id's : marketplace ids
        :param updated_after : date
        :param fulfillment_channels : amazon channel
        """
        kwargs = self.prepare_amazon_request_report_kwargs(seller,
                                                           'check_cancel_order_in_amazon_v13')
        kwargs.update({'marketplaceids': marketplaceids,
                       'updated_after': updated_after,
                       'fulfillment_channels': fulfillment_channels})

        response = iap_tools.iap_jsonrpc(DEFAULT_ENDPOINT + '/iap_request', params=kwargs, timeout=1000)
        if response.get('reason'):
            raise UserError(_(response.get('reason')))
        list_of_wrapper = response.get('result')
        return list_of_wrapper

    def cancel_amazon_draft_sales_order(self, seller, list_of_wrapper):
        """
        This function Cancels Amazon Pending Orders in ERP
        :param seller: amazon.seller.ept()
        :param list_of_wrapper: {}
        :return True: Boolean
        Updated by : Twinkalc 7th sep 2020.
        updated to process to cancel the amazon FBA and FBM orders with the single method
        removed separate method to cancel the FBM orders and pass the dynamic fulfillment_by.

        """
        ctx = self._context.copy() or {}
        fulfillment_by = ctx.get('fulfillment_by')

        log_book_obj = self.env['common.log.book.ept']
        comman_log_line_obj = self.env['common.log.lines.ept']
        model_id = comman_log_line_obj.get_model_id('sale.order')
        log_rec = log_book_obj.amazon_create_transaction_log('import', model_id, self.id)

        for wrapper_obj in list_of_wrapper:
            orders = []
            if not isinstance(wrapper_obj.get('Orders', {}).get('Order', []), list):
                orders.append(wrapper_obj.get('Orders', {}).get('Order', {}))
            else:
                orders = wrapper_obj.get('Orders', {}).get('Order', [])
            marketplace_instance_dict = {}
            for order in orders:
                order_status = order.get('OrderStatus', {}).get('value', '')
                if order_status != 'Canceled':
                    continue

                amazon_order_ref = order.get('AmazonOrderId', {}).get('value', False)
                if not amazon_order_ref:
                    continue

                marketplace_id = order.get('MarketplaceId', {}).get('value', False)
                instance = marketplace_instance_dict.get(marketplace_id)
                if not instance:
                    instance = seller.instance_ids.filtered(
                        lambda x: x.market_place_id == marketplace_id)
                    marketplace_instance_dict.update({marketplace_id: instance})

                existing_order = self.search([('amz_order_reference', '=', amazon_order_ref),
                                              ('amz_instance_id', '=', instance.id),
                                              ('state', '!=', 'cancel'),
                                              ('amz_fulfillment_by', '=', fulfillment_by)])
                if not existing_order:
                    message = 'Amazon order[%s] not Found in Odoo.' % (amazon_order_ref)
                    comman_log_line_obj.amazon_create_order_log_line( \
                        message, model_id, False, amazon_order_ref, False, fulfillment_by, log_rec)
                    continue

                if existing_order and existing_order.state == 'draft':
                    super(SaleOrder, existing_order).action_cancel()
                else:
                    message = 'Sale order %s not in draft state, only draft order can be ' \
                              'cancelled.' % (existing_order.name)
                    comman_log_line_obj.amazon_create_order_log_line( \
                        message, model_id, False, existing_order.name, False, fulfillment_by, log_rec)
        return True

    @staticmethod
    def prepare_amazon_prod_vals(instance, order_line, sku, odoo_product, fulfillment):
        """
        Prepare Amazon Product Values
        :param instance: amazon.instance.ept()
        :param order_line: {}
        :param sku: string
        :param odoo_product: product.product()
        :return: {}
        """
        prod_vals = {}
        if not odoo_product:
            prod_vals = {'name': order_line.get('Title', {}).get('value'), 'default_code': sku}

        prod_vals.update({
            'name': order_line.get('Title', {}).get('value'),
            'instance_id': instance.id,
            'product_asin': order_line.get('ASIN', {}).get('value', False),
            'seller_sku': sku,
            'product_id': odoo_product and odoo_product.id or False,
            'exported_to_amazon': True, 'fulfillment_by': fulfillment
        })
        return prod_vals

    def fba_pending_order_partner_dict(self, instance):
        """
        Create Dictionary of pending order partner
        default_fba_partner_id fetched according to seller wise
        :param instance:
        :return:
        """
        return {
            'invoice_partner': instance.seller_id.def_fba_partner_id and
                               instance.seller_id.def_fba_partner_id.id,
            'shipping_partner': instance.seller_id.def_fba_partner_id and
                                instance.seller_id.def_fba_partner_id.id,
            'pricelist_id': instance.pricelist_id and instance.pricelist_id.id}

    def create_amazon_pending_sales_order(self, seller, list_of_wrapper):
        """
        This Function Create Amazon Pending Orders with Draft state into ERP System
        :param seller: amazon.seller.ept()
        :param list_of_wrapper:
        :return:
        """
        log_book_obj = self.env['common.log.book.ept']
        comman_log_line_obj = self.env['common.log.lines.ept']

        marketplace_instance_dict = {}
        amazon_order_list = []
        product_details = {}
        model_id = comman_log_line_obj.get_model_id('shipping.report.request.history')
        log_rec = log_book_obj.amazon_create_transaction_log('import', model_id, \
                                                             self.id)
        for wrapper_obj in list_of_wrapper:
            orders = []
            if not isinstance(wrapper_obj.get('Orders', {}).get('Order', []), list):
                orders.append(wrapper_obj.get('Orders', {}).get('Order', {}))
            else:
                orders = wrapper_obj.get('Orders', {}).get('Order', [])

            for order in orders:
                amazon_order_ref = order.get('AmazonOrderId', {}).get('value', False)
                message, instance = self.check_amazon_order_vals_ept(seller, order,
                                                                     marketplace_instance_dict)
                if message:
                    comman_log_line_obj.amazon_create_order_log_line( \
                        message, model_id, False, amazon_order_ref, False, 'FBA', log_rec)
                    continue

                existing_order = self.search([('amz_order_reference', '=', amazon_order_ref),
                                              ('amz_instance_id', '=', instance.id),
                                              ('amz_fulfillment_by', '=', 'FBA')])
                if existing_order:
                    message = 'Order %s Already Exist in Odoo.' % (existing_order.name)
                    comman_log_line_obj.amazon_create_order_log_line( \
                        message, model_id, self.id, amazon_order_ref, False, 'FBA', log_rec)
                    continue

                self.request_fba_pending_sale_order_and_process_ept(seller, instance, order,
                                                                    product_details,
                                                                    amazon_order_list, log_rec)

        seller.fba_pending_order_last_sync_on = datetime.now()
        if not log_rec.log_lines:
            log_rec.unlink()
        return amazon_order_list

    def check_amazon_order_vals_ept(self, seller, order, marketplace_instance_dict):
        """
        This method will check  required amazon vals.
        """
        message = False
        amazon_order_ref = order.get('AmazonOrderId', {}).get('value', False)
        if not amazon_order_ref:
            message = 'Amazon Order Reference not found.'
            return message, False

        marketplace_id = order.get('MarketplaceId', {}).get('value', False)
        instance = marketplace_instance_dict.get(marketplace_id)
        if not instance:
            instance = seller.instance_ids.filtered( \
                lambda x: x.market_place_id == marketplace_id)
            marketplace_instance_dict.update({marketplace_id: instance})
            if not instance:
                message = 'Skipped due to Amazon Instance Not found.'
                return message, instance

        return message, instance

    def request_fba_pending_sale_order_and_process_ept(self, seller, instance, order,
                                                       product_details, amazon_order_list, log_rec):
        """
        This method will request for FBA pending sale order process the response to create
        sale order and sale order line.
        """
        sale_order_line_obj = self.env['sale.order.line']

        """default_fba_partner_id fetched according to seller wise"""
        amazon_order_ref = order.get('AmazonOrderId', {}).get('value', False)
        partner_dict = self.fba_pending_order_partner_dict(instance)

        kwargs = self.prepare_amazon_request_report_kwargs(seller, 'create_Sale_order_v13')
        kwargs.update({'amazon_order_ref': amazon_order_ref})

        response = iap_tools.iap_jsonrpc(DEFAULT_ENDPOINT + '/iap_request', params=kwargs, timeout=1000)
        if response.get('reason'):
            raise UserError(_(response.get('reason')))

        list_of_orderlines_wrapper = response.get('result')
        amazon_order = False
        skip_order = False
        order_lines = []
        for order_line_wrapper_obj in list_of_orderlines_wrapper:
            if not isinstance(
                    order_line_wrapper_obj.get('OrderItems', {}).get( \
                            'OrderItem', []),
                    list):
                order_lines.append(
                    order_line_wrapper_obj.get('OrderItems', {}).get( \
                        'OrderItem', {}))
            else:
                order_lines = order_line_wrapper_obj.get('OrderItems', {}).get(
                    'OrderItem', [])

            for order_line in order_lines:
                skip_order, product_details = self.with_context(
                    {'is_fba_order': True}).create_or_find_amazon_product( \
                    order_line, product_details, instance, amazon_order_ref, log_rec)
                if skip_order:
                    break

        if not skip_order:
            if not amazon_order:
                order_vals = self.create_amazon_sales_order_vals(partner_dict,
                                                                 order, instance)
                amazon_order = self.create(order_vals)
                amazon_order_list.append(amazon_order)

            for order_line in order_lines:
                line_data = self.prepare_fba_pending_order_line_ept(order_line)
                sale_order_line_obj.create_amazon_sale_order_line(amazon_order, \
                                                                  line_data, product_details)
            self.env.cr.commit()
        return True

    @staticmethod
    def prepare_fba_pending_order_line_ept(order_line):
        """
        Prepare Sale Order lines vals for amazon orders
        :param row:
        :param instance:
        :param product_details:
        :return:
        """

        return {
            'sku': order_line.get('SellerSKU', {}).get('value', False),
            'name': order_line.get('Title', {}).get('value', False),
            'product_uom_qty': order_line.get('QuantityOrdered', {}).get('value', 0.0),
            'amazon_order_qty': order_line.get('QuantityOrdered', {}).get('value', 0.0),
            'line_tax_amount': float(
                order_line.get('ItemTax', {}).get('Amount', {}).get('value', 0.0)),
            'amazon_order_item_id': order_line.get('OrderItemId', {}).get('value'),
            'item_price': float(
                order_line.get('ItemPrice', {}).get('Amount', {}).get('value', 0.0)),
            'tax_amount': float(order_line.get('ItemTax', {}).get('Amount', {}).get('value', 0.0)),
            'shipping_charge': float(
                order_line.get('ShippingPrice', {}).get('Amount', {}).get('value', 0.0)),
            'shipping_tax': float(
                order_line.get('ShippingTax', {}).get('Amount', {}).get('value', 0.0)),
            'gift_wrapper_charge': float(
                order_line.get('GiftWrapPrice', {}).get('Amount', {}).get('value', 0.0)),
            'gift_wrapper_tax': float(
                order_line.get('GiftWrapTax', {}).get('Amount', {}).get('value', 0.0)),
            'shipping_discount': float(
                order_line.get('ShippingDiscount', {}).get('Amount', {}).get('value', 0.0)),
            'promotion_discount': float(
                order_line.get('PromotionDiscount', {}).get('Amount', {}).get('value', 0.0)),
        }

    def amazon_sale_order_common_log(self, transaction_log_lines):
        """
        Create log to notify the user about different processes in Sale orders.
        :param transaction_log_lines: []
        :return: True
        """
        common_log_book_obj = self.env['common.log.book.ept']
        common_log_book_vals = {
            'type': 'import',
            'module': 'amazon_ept',
            'model_id': self.env['ir.model']._get('shipping.report.request.history').id,
            'res_id': self.id,
            'active': True,
            'log_lines': transaction_log_lines,
        }
        return common_log_book_obj.create(common_log_book_vals)

    @staticmethod
    def prepare_amazon_sale_order_vals(instance, partner_dict, order):
        """
        Prepares Sale Order Values for import in ERP
        :param instance: amazon.instance.ept()
        :param partner_dict: {}
        :param order: {}
        :return: {}
        """
        if order.get('PurchaseDate', {}).get('value', False):
            date_order = parser.parse(
                order.get('PurchaseDate', False).get('value', False)).astimezone(utc).strftime( \
                '%Y-%m-%d %H:%M:%S')
        else:
            date_order = time.strftime('%Y-%m-%d %H:%M:%S')

        return {'company_id': instance.company_id.id,
                'partner_id': partner_dict.get('invoice_partner'),
                'partner_invoice_id': partner_dict.get('invoice_partner'),
                'partner_shipping_id': partner_dict.get('shipping_partner'),
                'warehouse_id': instance.warehouse_id.id,
                'picking_policy': instance.picking_policy,
                'date_order': date_order or False,
                'pricelist_id': instance.pricelist_id.id or False,
                'payment_term_id': instance.seller_id.payment_term_id.id,
                'fiscal_position_id': instance.fiscal_position_id and
                                      instance.fiscal_position_id.id or False,
                'team_id': instance.team_id and instance.team_id.id or False,
                'client_order_ref': order.get('AmazonOrderId', {}).get('value', False),
                'carrier_id': False
                }

    @api.model
    def check_already_status_updated_in_amazon(self, seller, marketplaceids, instances):
        """Create Object for the integrate with amazon"""
        #warehouse_ids = list(set(map(lambda x: x.warehouse_id.id, instances))) no need to check warehouse
        sales_orders = self.search([('amz_order_reference', '!=', False),
                                    ('amz_instance_id', 'in', instances.ids), ('updated_in_amazon', '=', False),
                                    ('amz_fulfillment_by', '=', 'FBM')], order='date_order')
        if not sales_orders:
            return []
        updated_after_date = sales_orders[0].date_order - timedelta(+1)
        marketplaceids = tuple(marketplaceids)
        if updated_after_date:
            db_import_time = time.strptime(str(updated_after_date), "%Y-%m-%d %H:%M:%S")
            db_import_time = time.strftime("%Y-%m-%dT%H:%M:%S", db_import_time)
            start_date = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(
                time.mktime(time.strptime(db_import_time, "%Y-%m-%dT%H:%M:%S"))))
            updated_after_date = str(start_date) + 'Z'
        kwargs = self.prepare_amazon_request_report_kwargs(seller, 'check_already_status_updated_in_amazon_v13')
        kwargs.update({'marketplaceids': marketplaceids, 'updated_after': updated_after_date, })
        response = iap_tools.iap_jsonrpc(DEFAULT_ENDPOINT + '/iap_request', params=kwargs, timeout=1000)
        if response.get('reason'):
            raise UserError(_(response.get('reason')))
        list_of_wrapper = response.get('result')
        unshipped_sales_orders = self.prepare_amazon_fbm_unshipped_orders(list_of_wrapper, sales_orders)
        return unshipped_sales_orders

    def prepare_amazon_fbm_unshipped_orders(self, list_of_wrapper, sales_orders):
        """
        This method will prepare the list of amazon FBM unshipped orders.
        """
        list_of_amazon_order_ref = []
        for wrapper_obj in list_of_wrapper:
            orders = []
            if not isinstance(wrapper_obj.get('Orders', {}).get('Order', []), list):
                orders.append(wrapper_obj.get('Orders', {}).get('Order', {}))
            else:
                orders = wrapper_obj.get('Orders', {}).get('Order', [])
            for order in orders:
                amazon_order_ref = order.get('AmazonOrderId', {}).get('value', False)
                list_of_amazon_order_ref.append(amazon_order_ref)
        unshipped_sales_orders = []
        for order in sales_orders:
            if order.amz_order_reference not in list_of_amazon_order_ref:
                order.picking_ids.write({'updated_in_amazon': True})
            else:
                unshipped_sales_orders.append(order)
        return unshipped_sales_orders

    def cancel_order_in_amazon(self):
        """
        This method return the cancel order in amazon wizard.
        :return: Cancel Order Wizard
        """
        view = self.env.ref('amazon_ept.view_amazon_cancel_order_wizard')
        context = dict(self._context)
        context.update({'order_id': self.id})
        return {
            'name': _('Cancel Order In Amazon'),
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'amazon.cancel.order.wizard',
            'views': [(view.id, 'form')],
            'view_id': view.id,
            'target': 'new',
            'context': context
        }

    def get_header(self, instnace):
        """
        This method return the xml data header.
        :param instnace: instance object
        :return:xml header
        """
        return """<?xml version="1.0"?>
            <AmazonEnvelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" 
            xsi:noNamespaceSchemaLocation="amzn-envelope.xsd">
            <Header>
                <DocumentVersion>1.01</DocumentVersion>
                <MerchantIdentifier>%s</MerchantIdentifier>
            </Header>
            <MessageType>OrderAcknowledgement</MessageType>
         """ % (instnace.merchant_id)

    def get_message(self, lines, instance, order):
        """
        This method prepare the xml message.
        :param lines:sale order line object
        :param instance: instance object
        :param order: order object
        :return:message string
        """
        message_id = 1
        message_str = ''
        message_order_line = ''
        message = """ 
            <Message>
            <MessageID>%s</MessageID>
            <OrderAcknowledgement>
                 <AmazonOrderID>%s</AmazonOrderID>
                 <StatusCode>Failure</StatusCode>  
        """ % (message_id, order.amz_order_reference)
        for line in lines:
            message_order_line = """ 
                <Item> 
                <AmazonOrderItemCode>%s</AmazonOrderItemCode>
                <CancelReason>%s</CancelReason>
                <Quantity>%d</Quantity>
                </Item> 
            """ % (line.sale_line_id.amazon_order_item_id, line.message, int(line.ordered_qty))
            message = "%s %s" % (message, message_order_line)
            line.sale_line_id.write({'amz_return_reason': line.message})
        message = "%s </OrderAcknowledgement></Message>" % (message)

        message_str = "%s %s" % (message, message_str)
        header = self.get_header(instance)
        message_str = "%s %s </AmazonEnvelope>" % (header, message_str)
        return message_str

    def send_cancel_request_to_amazon(self, lines, instance, order):
        """
        This method will send cancel request to amazon.
        """
        data = self.get_message(lines, instance, order)
        account = self.env['iap.account'].search([('service_name', '=', 'amazon_ept')])
        dbuuid = self.env['ir.config_parameter'].sudo(
        ).get_param('database.uuid')

        kwargs = {'merchant_id': instance.merchant_id and str(instance.merchant_id) or False,
                  'auth_token': instance.auth_token and str(instance.auth_token) or False,
                  'app_name': 'amazon_ept',
                  'account_token': account.account_token,
                  'emipro_api': 'send_cancel_request_to_amazon_v13',
                  'dbuuid': dbuuid,
                  'amazon_marketplace_code': instance.country_id.amazon_marketplace_code or
                                             instance.country_id.code,
                  'marketplaceids': [instance.market_place_id],
                  'data': data, }

        response = iap_tools.iap_jsonrpc(DEFAULT_ENDPOINT + '/iap_request', params=kwargs, timeout=1000)
        if response.get('reason'):
            raise UserError(_(response.get('reason')))

        results = response.get('result')
        if results.get('FeedSubmissionInfo', {}).get('FeedSubmissionId', {}).get('value', False):
            last_feed_submission_id = results.get('FeedSubmissionInfo', {}).get('FeedSubmissionId',
                                                                                {}).get('value',
                                                                                        False)
            vals = {'message': data, 'feed_result_id': last_feed_submission_id,
                    'feed_submit_date': time.strftime("%Y-%m-%d %H:%M:%S"),
                    'instance_id': instance.id, 'user_id': self._uid,
                    'feed_type': 'cancel_request',
                    'seller_id': instance.seller_id.id}
            self.env['feed.submission.history'].create(vals)
        return True

    def create_or_find_amazon_product(self, order_details, product_details, instance,
                                      amazon_order_ref, log_book):
        """
        This method is find product in odoo based on sku. If not found than create new product.
        :param sku:Product SKU
        :param product_name:Product name or Description
        :param seller_id:Seller Object
        :param instance: instance Object
        :return: Odoo Product Object
        """
        product_obj = self.env['product.product']
        amz_product_obj = self.env['amazon.product.ept']
        comman_log_line_obj = self.env['common.log.lines.ept']
        product_model_id = self.env['ir.model']._get('product.product').id
        model_id = self.env['ir.model']._get('amazon.product.ept').id
        fulfillment_by = 'FBM'
        skip_order = False
        ctx = self._context.copy() or {}

        seller_sku = order_details.get('SellerSKU').get('value')
        if not seller_sku:
            skip_order = True
            message = 'Order skipped due to seller sku is not available'
            comman_log_line_obj.amazon_create_order_log_line(
                message, model_id, False, amazon_order_ref, seller_sku, fulfillment_by, log_book)
            return skip_order, product_details
        else:
            odoo_product = product_details.get((seller_sku, instance.id))
            if odoo_product:
                return skip_order, product_details

            if ctx.get('is_fba_order'):
                fulfillment_by = 'FBA'
            amazon_product = amz_product_obj.search_amazon_product(instance.id, seller_sku, fulfillment_by)
            if not amazon_product:
                odoo_product = amz_product_obj.search_product(seller_sku)
                if odoo_product:
                    message = 'Odoo Product is already exists. System have ' \
                              'created new Amazon Product %s for %s instance' % (
                                  seller_sku, instance.name)
                    comman_log_line_obj.amazon_create_order_log_line(
                        message, product_model_id, odoo_product.id, amazon_order_ref, seller_sku,
                            fulfillment_by, log_book)
                elif not instance.seller_id.create_new_product:
                    skip_order = True
                    message = 'Product %s not found for %s instance' % (
                        seller_sku, instance.name)
                    comman_log_line_obj.amazon_create_order_log_line(
                        message, model_id, False, amazon_order_ref, seller_sku, fulfillment_by, log_book)
                else:
                    # #Create Odoo Product
                    erp_prod_vals = {
                        'name': order_details.get('Title').get('value'),
                        'default_code': seller_sku,
                        'type': 'product',
                        'purchase_ok': True,
                        'sale_ok': True,
                    }
                    odoo_product = product_obj.create(erp_prod_vals)
                    message = 'System have created new Odoo Product %s for %s instance' % (
                        seller_sku, instance.name)
                    comman_log_line_obj.amazon_create_order_log_line(
                        message, product_model_id, False, amazon_order_ref, seller_sku, fulfillment_by, log_book)

                if not skip_order:
                    sku = seller_sku or (odoo_product and odoo_product[0].default_code) or False
                    # #Prepare Product Values
                    prod_vals = self.prepare_amazon_prod_vals(instance, order_details, sku,
                                                              odoo_product, fulfillment_by)
                    # #Create Amazon Product
                    amz_product_obj.create(prod_vals)
                if odoo_product:
                    product_details.update({(seller_sku, instance.id): odoo_product})
            else:
                product_details.update({(seller_sku, instance.id): amazon_product.product_id})

            return skip_order, product_details

    def prepare_amazon_customer_vals(self, row):
        """
        This method prepare the customer vals
        :param row: row of data
        :return: customer vals
        """
        return {
            'BuyerEmail': row.get('BuyerEmail').get('value'),
            'BuyerName': row.get('BuyerName').get('value'),
            'ShipNumber': row.get('ShippingAddress').get('Phone').get('value') if row.get( \
                'ShippingAddress').get( \
                'Phone') else None,
            'AddressLine1': row.get('ShippingAddress').get('AddressLine1').get('value') if row.get(
                'ShippingAddress').get('AddressLine1') else None,
            'City': row.get('ShippingAddress').get('City').get('value') if row.get( \
                'ShippingAddress').get( \
                'City') else None,
            'ShipName': row.get('ShippingAddress').get('Name').get('value') if row.get( \
                'ShippingAddress').get( \
                'Name') else None,
            'CountryCode': row.get('ShippingAddress').get('CountryCode').get('value') if row.get( \
                'ShippingAddress').get( \
                'CountryCode') else '',
            'StateOrRegion': row.get('ShippingAddress').get('StateOrRegion').get( \
                'value') if row.get( \
                'ShippingAddress').get('StateOrRegion') else None,
            'PostalCode': row.get('ShippingAddress').get('PostalCode').get('value') if row.get( \
                'ShippingAddress').get( \
                'PostalCode') else None,
            'AddressType': row.get('ShippingAddress').get('AddressType').get('value') if row.get( \
                'ShippingAddress').get( \
                'AddressType') else None,
            'AmazonOrderId': row.get('AmazonOrderId').get('value') if row.get( \
                'AmazonOrderId') else None,
        }

    def prepare_updated_ordervals(self, instance, order_ref, order):
        """
        This method prepare the order vals.
        :param expected_delivery_date: Expected Delivery Date
        :param instance: instance object
        :param seller: seller object
        :param order_ref: order reference
        :return: Order Vals
        """

        is_business_order = True if order.get('IsBusinessOrder', {}).get('value', '').lower() in [
            'true', 't'] else False
        is_prime_order = True if order.get('IsPrime', {}).get('value', '').lower() in ['true',
                                                                                       't'] else False

        ordervals = {
            'amz_instance_id': instance and instance.id or False,
            'amz_seller_id': instance.seller_id.id,
            'amz_fulfillment_by': 'FBM',
            'amz_order_reference': order_ref or order_ref[0] or False,
            'auto_workflow_process_id': instance.seller_id.fbm_auto_workflow_id.id,
            'is_business_order': is_business_order,
            'is_prime_order': is_prime_order,
            'amz_shipment_service_level_category': order.get('ShipmentServiceLevelCategory', {}).get('value', False)
        }
        return ordervals

    def get_item_price(self, unit_price, tax):
        """
        This method addition the price and tax of product item cost.
        :param unit_price: item price
        :param tax: item tax
        :return: sum of price and tax.
        """
        if self.amz_seller_id.is_vcs_activated or not self.amz_instance_id.amz_tax_id.price_include:
            return unit_price
        return unit_price + tax

    def amz_create_order_lines(self, order, instance, order_details, dict_product_details):
        """
        This method prepare order lines.
        :param order: order Object
        :param instance: instance object
        :param order_details: sale order line from dictionary
        :param sale_order_line_obj: sale order line object
        :return: True
        """
        taxargs = {}
        product = dict_product_details.get(
            (order_details.get('SellerSKU', {}).get('value', ''), instance.id))
        quantity = float(order_details.get('QuantityOrdered', {}).get('value', 1.0))
        unit_price = float(order_details.get('ItemPrice', {}).get('Amount', {}).get('value', 0.0)) / quantity
        item_price = order.get_item_price(unit_price, float(
            order_details.get('ItemTax', {}).get('Amount', {}).get('value', 0.0)))
        item_tax = float(order_details.get('ItemTax', {}).get('Amount', {}).get('value', 0.00))
        if order.amz_instance_id.is_use_percent_tax:
            unit_tax = item_tax / quantity if quantity > 0.0 else item_tax
            item_tax_percent = (unit_tax * 100) / unit_price if unit_price > 0 else 0.00
            amz_tax_id = order.amz_instance_id.amz_tax_id
            item_price = unit_price
            taxargs = {'line_tax_amount_percent': item_tax_percent, 'tax_id': [(6, 0, amz_tax_id.id and [
                amz_tax_id.id] or [])]}

        line_vals = {
            'order_id': order.id,
            'product_id': product.id,
            'company_id': instance.company_id.id or False,
            'name': product.description_sale,
            'order_qty': order_details.get('QuantityOrdered', {}).get('value', 0.0),
            'price_unit': item_price,
            'product_uom_qty': order_details.get('QuantityShipped', {}).get('value', 0.0),
            'product_uom': product and product.product_tmpl_id.uom_id.id,
            'discount': 0.0
        }
        order_line_vals = order.order_line.create_sale_order_line_ept(line_vals)
        order_line_vals.update({
            'amazon_order_item_id': order_details.get('OrderItemId', {}).get('value', ''),
            'line_tax_amount': item_tax,
            **taxargs
        })
        order.order_line.create(order_line_vals)

        ## Shipping Charge Line
        self.get_fbm_shipped_order_line(instance, order, order_details)

        ## Shipping Charge Discount Line
        self.get_fbm_shipped_discount_order_line(instance, order, order_details)

        ## Promotion Discount Line
        self.get_fbm_promotion_discount_line(instance, order, order_details)
        return True

    def get_fbm_shipped_order_line(self, instance, order, order_details):
        """
        This method will prepare the values of shipped order lines and create that.
        """
        if order_details.get('ShippingPrice', False) and float(
                order_details.get('ShippingPrice', {}).get('Amount', {}).get(
                    'value', 0.0)) > 0 and instance.seller_id.shipment_charge_product_id:
            shipping_price = float(
                order_details.get('ShippingPrice', {}).get('Amount', {}).get('value', 0.0))
            ship_tax = float(order_details.get('ShippingTax').get('Amount', {}).get('value', 0.0))

            ship_total, shipargs = self.get_amazon_fbm_shippig_vals_ept(instance, order,
                                                                        shipping_price, ship_tax)

            shipping_vals = {
                'order_id': order.id,
                'product_id': instance.seller_id.shipment_charge_product_id.id,
                'company_id': instance.company_id.id or False,
                'name': instance.seller_id.shipment_charge_product_id.description_sale or False,
                'order_qty': '1.0',
                'price_unit': ship_total,
                'discount': False,
                'is_delivery': True
            }
            ship_line_vals = order.order_line.create_sale_order_line_ept(shipping_vals)
            ship_line_vals.update({
                'amazon_order_item_id': order_details.get('OrderItemId').get('value') + "_ship",
                'amz_shipping_charge_ept': ship_total,
                'amz_shipping_charge_tax': ship_tax,
                **shipargs
            })
            order.order_line.create(ship_line_vals)
        return True

    def get_amazon_fbm_shippig_vals_ept(self, instance, order, shipping_price, ship_tax):
        """
        This method will get prepare the ship args and return that.
        """
        if order.amz_seller_id.is_vcs_activated or not instance.amz_tax_id.price_include:
            ship_total = shipping_price
        else:
            ship_total = shipping_price + ship_tax

        shipargs = {}
        if instance.is_use_percent_tax:
            item_tax_percent = (ship_tax * 100) / ship_total
            amz_tax_id = order.amz_instance_id.amz_tax_id
            shipargs = {'line_tax_amount_percent': item_tax_percent,
                        'tax_id': [(6, 0, [amz_tax_id.id])]}

        return ship_total, shipargs

    def get_fbm_shipped_discount_order_line(self, instance, order, order_details):
        """
        This method will prepare the FBM shipped discount order lines.
        """
        if order_details.get('ShippingDiscount', False) and float(
                order_details.get('ShippingDiscount').get('Amount', {}).get(
                    'value')) < 0 and instance.seller_id.ship_discount_product_id:
            shipping_price = float(
                order_details.get('ShippingDiscount').get('Amount', {}).get('value', 0.0))
            disc_tax = float(
                order_details.get('ShippingDiscountTax').get('Amount', {}).get('value', 0.0))
            discargs = {}
            discount_price = shipping_price - disc_tax
            if instance.is_use_percent_tax:
                discount_price = shipping_price
                gift_tax_percent = (disc_tax * 100) / discount_price
                amz_tax_id = order.amz_instance_id.amz_tax_id
                discargs = {'line_tax_amount_percent': abs(gift_tax_percent),
                            'tax_id': [(6, 0, [amz_tax_id.id])]}

            product_id = instance.seller_id.shipment_charge_product_id
            ship_disc_vals = self.create_fbm_shipped_chargable_order_line(order, instance,
                                                                          product_id,
                                                                          discount_price)
            ship_disc_line_vals = order.order_line.create_sale_order_line_ept(ship_disc_vals)
            ship_disc_line_vals.update({
                'amz_shipping_discount_ept': discount_price,
                'amazon_order_item_id': order_details.get('OrderItemId').get(
                    'value') + "_ship_discount",
                **discargs
            })
            order.order_line.create(ship_disc_line_vals)
        return True

    def get_fbm_promotion_discount_line(self, instance, order, order_details):
        """
        This method will create promotion discount lines.
        """
        if order_details.get('PromotionDiscount', False) and float(
                order_details.get('PromotionDiscount').get('Amount', {}).get(
                    'value')) > 0 and instance.seller_id.promotion_discount_product_id:
            item_discount = float(
                order_details.get('PromotionDiscount').get('Amount', {}).get(
                    'value', 0.0)) * (-1)
            discount_tax = float(
                order_details.get('PromotionDiscountTax').get('Amount', {}).get(
                    'value', 0.0))
            discount = item_discount - discount_tax
            product_id = instance.seller_id.promotion_discount_product_id
            promo_disc_vals = self.create_fbm_shipped_chargable_order_line(
                order, instance,
                product_id, discount)
            promo_disc_line_vals = order.order_line.create_sale_order_line_ept(
                promo_disc_vals)
            promo_disc_line_vals.update({
                'amz_promotion_discount': discount,
                'amazon_order_item_id': order_details.get('OrderItemId').get(
                    'value') + '_promo_discount'
            })
            order.order_line.create(promo_disc_line_vals)
        return True

    def create_fbm_shipped_chargable_order_line(self, order, instance, product_id, price_unit):
        """
        This method will create shipped chargeable order lines
        """
        chargable_vals = {
            'order_id': order.id,
            'product_id': product_id.id,
            'company_id': instance.company_id.id or False,
            'name': product_id.description_sale or product_id.name,
            'order_qty': '1.0',
            'price_unit': price_unit,
            'discount': True}
        return chargable_vals

    def prepare_amazon_request_report_kwargs(self, seller_id, emipro_api):
        """
        Prepare General Amazon Order Request Dict.
        @author: Twinkal Chandarana
        :param emipro_api : Request to get response based on api
        :return: {}
        """
        account = self.env['iap.account'].search([('service_name', '=', 'amazon_ept')])
        dbuuid = self.env['ir.config_parameter'].sudo().get_param('database.uuid')

        return {'merchant_id': seller_id.merchant_id and str(seller_id.merchant_id) or False,
                'auth_token': seller_id.auth_token and str(seller_id.auth_token) or False,
                'app_name': 'amazon_ept',
                'account_token': account.account_token,
                'emipro_api': emipro_api,
                'dbuuid': dbuuid,
                'amazon_marketplace_code': seller_id.country_id.amazon_marketplace_code or
                                           seller_id.country_id.code}

    def amz_create_sales_order(self, queue_order, log_book):
        """
        This method create the sale orders in odoo.
        :param queue_order: shipped.order.data.queue.ept()
        :param account: iap.account()
        :param dbuuid: ir.config_parameter()
        :param log_book: common.log.book.ept()
        :return: True
        """
        common_log_line_ept = self.env['common.log.lines.ept']
        marketplace_instance_dict = dict()
        request_counter = 0
        model_id = self.env['ir.model']._get('sale.order').id
        seller = queue_order.amz_seller_id
        queue_lines = queue_order.shipped_order_data_queue_lines.filtered(lambda x: x.state != 'done')
        module_obj = self.env['ir.module.module']
        vat_module = module_obj.sudo().search([('name', '=', 'base_vat'), ('state', '=', 'installed')])
        for line in queue_lines:
            order = json.loads(line.order_data_id)
            amazon_order_ref = order.get('AmazonOrderId', {}).get('value', False)
            message, instance = self.check_amazon_order_vals_ept(seller, order, marketplace_instance_dict)
            if message:
                common_log_line_ept.amazon_create_order_log_line(message, model_id, False,
                                                                 amazon_order_ref, False, 'FBM', log_book)
                line.state = 'failed'
                continue
            if not order.get('PurchaseDate').get('value'):
                message = 'Skipped due to Purchase Date Not found.'
                common_log_line_ept.amazon_create_order_log_line(message, model_id, False,
                                                                 amazon_order_ref, False, 'FBM', log_book)
                line.state = 'failed'
                continue
            fulfillment_channel = order.get('FulfillmentChannel', {}).get('value', False)
            if fulfillment_channel and fulfillment_channel == 'AFN' and \
                    not hasattr(instance, 'fba_warehouse_id'):
                message = 'Skipped because of Fulfillment Channel is AFN'
                common_log_line_ept.amazon_create_order_log_line(message, \
                                                                 model_id, False, amazon_order_ref,
                                                                 False, 'FBM', log_book)
                line.state = 'failed'
                continue
            existing_order = self.search([('amz_order_reference', '=', amazon_order_ref),
                                          ('amz_instance_id', '=', instance.id),
                                          ('amz_fulfillment_by', '=', 'FBM')])
            if existing_order:
                line.state = 'done'
                continue
            kwargs = self.prepare_amazon_request_report_kwargs(seller, 'create_Sale_order_v13')
            kwargs.update({'amazon_order_ref': amazon_order_ref})
            request_counter += 1
            if request_counter >= 25:
                request_counter = 0
                time.sleep(5)
            response = iap_tools.iap_jsonrpc(DEFAULT_ENDPOINT + '/iap_request', params=kwargs, timeout=1000)
            if response.get('reason'):
                raise UserError(_(response.get('reason')))

            list_of_shipped_order_lines = response.get('result')
            self.process_shipped_or_missing_unshipped_lines_ept(instance, order, line,
                                                        list_of_shipped_order_lines, log_book)
        return True

    def get_fbm_next_token_orders(self, seller, next_token):
        """
        This method will request for amazon order by next token and return response.
        """
        kwargs = self.prepare_amazon_request_report_kwargs(seller, 'amz_order_by_next_token')
        kwargs.update({'next_token': next_token, })
        response = iap_tools.iap_jsonrpc(DEFAULT_ENDPOINT + '/iap_request', params=kwargs, timeout=1000)
        if response.get('reason'):
            raise response.get('reason')

        orders = response.get('result', [])
        return orders

    def process_shipped_or_missing_unshipped_lines_ept(self, instance, order, line,
                                               list_of_shipped_order_lines, log_book):
        """
        This method will process amazon shipped order lines.
        """
        common_log_line_ept = self.env['common.log.lines.ept']
        model_id = self.env['ir.model']._get('sale.order').id
        created_order_list = []
        line_state = line.state
        order_status =  order.get('OrderStatus', {}).get('value', '')

        order_counter = 0
        for order_line_wrapper_obj in list_of_shipped_order_lines:
            order_lines = []
            if not isinstance(order_line_wrapper_obj.get('OrderItems', {}).get( \
                    'OrderItem', []), list):
                order_lines.append(
                    order_line_wrapper_obj.get('OrderItems', {}).get( \
                        'OrderItem', {}))
            else:
                order_lines = order_line_wrapper_obj.get('OrderItems', {}).get(
                    'OrderItem', [])
            sales_order, line_state = self.process_shipped_or_missing_unshipped_order_ept(instance, order, \
                                                                            order_lines, line_state,
                                                                            log_book)
            if sales_order:
                created_order_list.append(sales_order)
                if order_status == 'Shipped':
                    sales_order.amz_seller_id.fbm_auto_workflow_id.shipped_order_workflow_ept(sales_order)
                elif order_status in ['Unshipped', 'PartiallyShipped']:
                    sales_order.process_orders_and_invoices_ept()
                else:
                    message = 'Workflow not executed for order %s because order status is %s' % (
                            sales_order.amz_order_reference, order_status)
                    common_log_line_ept.amazon_create_order_log_line(message, model_id, False,
                                                                     sales_order.amz_order_reference, False, 'FBM', log_book)
            line.state = line_state
            order_counter += 1
            if order_counter >= 10:
                self._cr.commit()
                order_counter = 0
        return True

    def process_shipped_or_missing_unshipped_order_ept(self, instance, order, order_lines, line_state, log_book):
        """
        This method will process amazon shipped orders.
        """
        partner = {}
        state_dict = dict()
        country_dict = dict()
        dict_product_details = dict()
        count_order_number = 0
        sales_order = self.browse()

        fbm_sale_order_report_obj = self.env['fbm.sale.order.report.ept']
        common_log_line_ept = self.env['common.log.lines.ept']

        amazon_order_ref = order.get('AmazonOrderId', {}).get('value', False)
        seller_id = instance.seller_id
        model_id = self.env['ir.model']._get('sale.order').id

        for order_line in order_lines:
            skip_order, dict_product_details = self.create_or_find_amazon_product( \
                order_line, dict_product_details, instance, amazon_order_ref, log_book)
            if skip_order:
                line_state = 'failed'
                break

            # Skip order line if ordered quantity is 0.
            if float(order_line.get('QuantityOrdered').get('value', 0.0)) == 0.0:
                message = 'Skipped Order line because of 0 Quantity Ordered.'
                common_log_line_ept.amazon_create_order_log_line(message, model_id,
                                                                 False, amazon_order_ref, False, 'FBM', log_book)
                line_state = 'failed'
                continue

            if not sales_order or sales_order.amz_order_reference != amazon_order_ref:
                if order.get('BuyerEmail').get('value'):
                    customer_vals = self.prepare_amazon_customer_vals(order)
                    vat, vat_country_code =  self.get_amazon_tax_registration_details(order)
                    customer_vals.update({'vat-number': vat, 'vat-country': vat_country_code,
                                          'check_vat_ept': order.get('check_vat_ept', False)})

                    partner = fbm_sale_order_report_obj.get_partner(customer_vals, state_dict,
                                                                                  country_dict, instance)
                if partner:
                    vals = self.prepare_amazon_sale_order_vals(instance, partner, order)
                    ordervals = self.create_sales_order_vals_ept(vals)
                    if not seller_id.is_default_odoo_sequence_in_sales_order:
                        name = seller_id.order_prefix + amazon_order_ref if seller_id.order_prefix else \
                            amazon_order_ref
                        ordervals.update({'name': name})
                    updated_ordervals = self.prepare_updated_ordervals(instance, amazon_order_ref, order)
                    ordervals.update(updated_ordervals)
                    sales_order = self.create(ordervals)
                    count_order_number += 1
            self.amz_create_order_lines(sales_order, instance, order_line, dict_product_details)
            line_state = 'done'
        return sales_order, line_state

    def get_fbm_orders(self, seller, marketplaceids, orderstatus, updated_after_date):
        """
        This method will request for amazon orders and return response.
        """
        kwargs = self.prepare_amazon_request_report_kwargs(seller, 'import_sales_order_v13')
        kwargs.update({'marketplaceids': marketplaceids,
                       'updated_after_date': updated_after_date,
                       'orderstatus': orderstatus})
        response = iap_tools.iap_jsonrpc(DEFAULT_ENDPOINT + '/iap_request', params=kwargs, timeout=1000)
        if response.get('reason'):
            raise UserError(_(response.get('reason')))
        result = response.get('result')
        return result

    def create_shipped_or_missing_unshipped_queue(self, datas, instance_dict, seller, data_queue):
        """
        This method will create an shipped order queue.
        """
        shipped_order_data_queue_line_obj = self.env['shipped.order.data.queue.line.ept']
        for data in datas:
            instance = instance_dict.get(data.get('SalesChannel').get('value'))
            if not instance:
                instance = seller.mapped('instance_ids').filtered(
                    lambda l: l.marketplace_id.name == data.get('SalesChannel').get('value'))
                instance_dict.update({data.get('SalesChannel').get('value'): instance})
            shipped_order_data_queue_line_obj.create({
                'order_id': data.get('AmazonOrderId').get('value'),
                'order_data_id': json.dumps(data),
                'amz_instance_id': instance.id,
                'last_process_date': datetime.now(),
                'shipped_order_data_queue_id': data_queue.id
            })
        return True

    def import_fbm_shipped_or_missing_unshipped_orders(self, seller, instance, updated_after_date, orderstatus):
        """
        This method process the FBM shipped orders.
        :param seller: seller object
        :param instance: instance object
        :param start_date: start date from where to get the orders
        :param end_date: until this date get the orders.
        :return: True
        """
        shipped_order_data_queue_obj = self.env['shipped.order.data.queue.ept']
        instance_dict = {}
        if not instance:
            marketplaceids = tuple(map(lambda x: x.market_place_id, seller.instance_ids))
        else:
            marketplaceids = tuple(map(lambda x: x.market_place_id, instance))
        if not marketplaceids:
            raise UserError(
                _("There is no any instance is configured of seller %s") % (seller.name))

        if updated_after_date:
            updated_after_date = updated_after_date.strftime("%Y-%m-%d %H:%M:%S")
            db_import_time = time.strptime(str(updated_after_date), "%Y-%m-%d %H:%M:%S")
            db_import_time = time.strftime("%Y-%m-%dT%H:%M:%S", db_import_time)
            updated_after_date = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(
                time.mktime(time.strptime(db_import_time, "%Y-%m-%dT%H:%M:%S"))))
            updated_after_date = str(updated_after_date) + 'Z'
        else:
            today = datetime.now()
            earlier = today - timedelta(days=3)
            earlier_str = earlier.strftime("%Y-%m-%dT%H:%M:%S")
            updated_after_date = earlier_str + 'Z'

        result = self.get_fbm_orders(seller, marketplaceids, orderstatus, updated_after_date)
        next_token = result.get('NextToken', {}).get('value')
        data_queue = shipped_order_data_queue_obj.create({'amz_seller_id': seller.id})
        datas = result.get('Orders', {}).get('Order', {})
        if not isinstance(datas, list) and datas:
            datas = [datas]
        if not datas:
            return True
        self.create_shipped_or_missing_unshipped_queue(datas, instance_dict, seller, data_queue)
        self._cr.commit()
        if data_queue.shipped_order_data_queue_lines:
            cron_id = self.env.ref('amazon_ept.ir_cron_child_to_process_shipped_order_queue_line')
            if cron_id and not cron_id.sudo().active:
                cron_id.sudo().write({'active': True, 'nextcall': datetime.now()})
            elif cron_id:
                try:
                    cron_id.sudo().write({'nextcall': datetime.now()})
                except Exception as e:
                    _logger.debug("Method %s will be called after commit", e)
        while True:
            if not next_token:
                break
            result = self.get_fbm_next_token_orders(seller, next_token)
            datas = result.get('Orders', {}).get('Order', {})
            next_token = result.get('NextToken', {}).get('value', False)
            if not isinstance(datas, list) and datas:
                datas = [datas]
            if datas:
                data_queue = shipped_order_data_queue_obj.create({'amz_seller_id': seller.id})
                self.create_shipped_or_missing_unshipped_queue(datas, instance_dict, seller, data_queue)
                self._cr.commit()
        return True

    @staticmethod
    def prepare_sale_order_update_values(instance, order):
        """
        Prepares Sale Order Values
        :param instance: amazon.instance.ept()
        :param order: {}
        :return: {}
        """
        is_business_order = True if order.get('IsBusinessOrder', {}).get('value', '').lower() in [
            'true', 't'] else False
        is_prime_order = True if order.get('IsPrime', {}).get('value', '').lower() in ['true',
                                                                                       't'] else False

        return {
            'auto_workflow_process_id': instance.seller_id.fba_auto_workflow_id.id or False,
            'amz_instance_id': instance and instance.id or False,
            'amz_fulfillment_by': 'FBA',
            'amz_order_reference': order.get('AmazonOrderId', {}).get('value', False),
            'amz_seller_id': instance.seller_id and instance.seller_id.id or False,
            'is_business_order': is_business_order,
            'is_prime_order': is_prime_order
        }

    def create_amazon_sales_order_vals(self, partner_dict, order, instance):
        """
        This function Creates Sale Orders values
        and pass the values to common connector library for import orders in odoo
        :param partner_dict: {}
        :param order: {}
        :param instance: amazon.instance.ept()
        :return: {}
        """

        sale_order_obj = self.env['sale.order']
        # #Prepare Sale Order Values
        vals = self.prepare_amazon_sale_order_vals(instance, partner_dict, order)
        # #Create Sale Orders from Common Connector library
        ordervals = sale_order_obj.create_sales_order_vals_ept(vals)
        # #Prepare Sale Order values for update
        sale_order_values = self.prepare_sale_order_update_values(instance, order)
        sale_order_values.update({'is_fba_pending_order': True})
        ordervals.update(sale_order_values)
        # #is_default_odoo_sequence_in_sale_order, order_prefix is fetched according to seller wise
        if not instance.seller_id.is_default_odoo_sequence_in_sales_order:
            ordervals.update({'name': "%s%s" % (
                instance.seller_id.fba_order_prefix and instance.seller_id.fba_order_prefix or '',
                order.get('AmazonOrderId', {}).get('value'))})
        # merge with FBA
        fulfillment_vals = self.fba_fulfillment_prepare_vals(instance)
        ordervals.update(fulfillment_vals)
        return ordervals

    @staticmethod
    def fba_fulfillment_prepare_vals(instance):
        """
        Prepare values for FBA Fulfillment workflow process
        fba_auto_workflow_id is fetched according to seller wise
        :param instance: amazon.instance.ept()
        :return: {}
        """
        workflow = instance.seller_id.fba_auto_workflow_id or \
                   instance.seller_id.fba_auto_workflow_id
        return {
            'warehouse_id': instance.fba_warehouse_id and
                            instance.fba_warehouse_id.id or instance.warehouse_id.id,
            'auto_workflow_process_id': workflow.id,
            'amz_fulfillment_by': 'FBA',
            'picking_policy': workflow.picking_policy,
            'seller_id': instance.seller_id and instance.seller_id.id or False,
        }

    def create_amazon_shipping_report_sale_order(self, row, partner, report_id):
        """
        Process Amazon Shipping Report Sale Orders
        :param instance: amazon.instance.ept()
        :param warehouse: warehouse id
        :param row: file_data {}
        :param partner: partners {}
        :return: sale.order()
        """
        amz_instance_obj = self.env['amazon.instance.ept']
        instance = amz_instance_obj.browse(row.get('instance_id'))
        warehouse = row.get('warehouse', False) or instance.fba_warehouse_id and \
                    instance.fba_warehouse_id.id or \
                    instance.warehouse_id.id

        amazon_exist_order = self.search([
            ('amz_order_reference', '=', row.get('amazon-order-id', '')), \
            ('amz_instance_id', '=', instance.id), ('warehouse_id', '=', warehouse)], \
            order="id desc", limit=1)
        if amazon_exist_order:
            return amazon_exist_order

        order_vals = self.prepare_amazon_sale_order_vals(instance, partner, row)
        carrier_id = False
        if row.get('carrier', ''):
            # #shipment_charge_product_id is fetched according to seller wise
            carrier_id = self.get_amz_shipping_method(row.get('carrier', ''),
                                                      instance.seller_id.shipment_charge_product_id)
        if row.get('purchase-date', False):
            date_order = parser.parse(row.get('purchase-date', False)) \
                .astimezone(utc).strftime('%Y-%m-%d %H:%M:%S')
        else:
            date_order = time.strftime('%Y-%m-%d %H:%M:%S')
        order_vals.update(
            {'warehouse_id': warehouse,
             'client_order_ref': row.get('amazon-order-id', '') or False,
             'date_order': date_order,
             'carrier_id': carrier_id
             })
        # #Create Sale Orders from Common Connector library
        ordervals = self.create_sales_order_vals_ept(order_vals)
        # #Prepare Sale Order values for update
        sale_order_values = self.prepare_sale_order_update_values(instance, row)
        sale_order_values.update({
            'amz_order_reference': row.get('amazon-order-id', False),
            'amz_shipment_service_level_category': row.get('ship-service-level', False),
            'amz_shipment_report_id': report_id})
        ordervals.update(sale_order_values)
        if not instance.seller_id.is_default_odoo_sequence_in_sales_order_fba:
            ordervals.update(
                {'name': "%s%s" % (
                    instance.seller_id.fba_order_prefix or '',
                    row.get('amazon-order-id', ''))})

        return self.create(ordervals)

    def get_amz_shipping_method(self, ship_method, ship_product):
        """
        Find or create Delivery Carrier as per carrer code in shipment report
        :param ship_method:
        :param ship_product:
        :return carrier.id: delivery carrier id
        """
        delivery_carrier_obj = self.env['delivery.carrier']
        ship_method = ship_method.replace(' ', '')
        carrier = delivery_carrier_obj.search(['|', ('amz_carrier_code', '=', ship_method),
                                               ('name', '=', ship_method)], limit=1)
        if not carrier:
            carrier = delivery_carrier_obj.create({
                'name': ship_method,
                'product_id': ship_product.id})
        return carrier.id

    def create_outbound_shipment(self):
        """
        This method is used to create outbound shipment.
        """
        amazon_outbound_order_wizard_obj = self.env['amazon.outbound.order.wizard']
        outbound_order_vals = {"sale_order_ids": [(6, 0, [self.id])]}
        instance_id = self.warehouse_id.seller_id.instance_ids.filtered(
            lambda x: x.fba_warehouse_id == self.warehouse_id and
                      x.country_id == self.warehouse_id.partner_id.country_id)
        if not instance_id:
            instance_id = self.warehouse_id.seller_id.instance_ids.filtered(
                lambda x: x.fba_warehouse_id == self.warehouse_id)
        if instance_id:
            outbound_order_vals.update({"instance_id": instance_id[0].id})
        created_id = amazon_outbound_order_wizard_obj.with_context(
            {'active_model': self._name, 'active_ids': self.ids,
             'active_id': self.id or False}).create(outbound_order_vals)
        return amazon_outbound_order_wizard_obj.wizard_view(created_id)

    def amz_update_tracking_number(self, seller):
        """
        Check If Order already shipped in the amazon then we will skip that all orders and set update_into_amazon=True
        :param seller: amazon.seller.ept()
        :return: True
        @author: Keyur Kanani
        """
        marketplaceids = seller.instance_ids.mapped(lambda l: l.marketplace_id.market_place_id)
        if not marketplaceids:
            raise UserError(_("There is no any instance is configured of seller %s" % (seller.name)))
        amazon_orders = self.check_already_status_updated_in_amazon(seller, marketplaceids, seller.instance_ids)
        if not amazon_orders:
            return []
        message_information, shipment_pickings = self.get_amz_message_information_ept(amazon_orders)
        if not message_information:
            return True
        data = self.create_data(message_information, str(seller.merchant_id))
        kwargs = self.prepare_amazon_request_report_kwargs(seller, 'amz_update_order_status_v13')
        kwargs.update({'data': data, 'marketplaceids': marketplaceids})
        response = iap_tools.iap_jsonrpc(DEFAULT_ENDPOINT + '/iap_request', params=kwargs, timeout=1000)
        if response.get('reason'):
            raise UserError(_(response.get('reason')))
        else:
            results = response.get('result', {})
        self.process_amazon_update_tracking_feed_response(results, data, seller, shipment_pickings)
        return True

    def process_amazon_update_tracking_feed_response(self, results, data, seller, shipment_pickings):
        """
        Process result of API after updating tracking number feed to Amazon.
        :param results: dict{}
        :param data: xml string
        :param seller:amazon.seller.ept()
        :param shipment_pickings: list[pickings]
        @author: Keyur Kanani
        """
        picking_obj = self.env['stock.picking']
        if results.get('FeedSubmissionInfo', {}).get('FeedSubmissionId', {}).get('value', False):
            feed_submission_obj = self.env['feed.submission.history']
            feed_submission_id = results.get('FeedSubmissionInfo', {}).get('FeedSubmissionId', {}).get('value',False)
            vals = {'message': data.encode('utf-8'), 'feed_result_id': feed_submission_id,
                    'feed_submit_date': time.strftime("%Y-%m-%d %H:%M:%S"), 'user_id': self._uid,
                    'seller_id': seller.id, 'feed_type': 'update_tracking_number'}
            feed_id = feed_submission_obj.create(vals)
            if feed_id:
                picking_obj.browse(shipment_pickings).write({'feed_submission_id': feed_id.id})
                cron_id = self.env.ref('amazon_ept.ir_cron_get_feed_submission_result')
                if cron_id and not cron_id.sudo().active:
                    cron_id.sudo().write(
                        {'active': True, 'nextcall': datetime.now() + timedelta(minutes=5)})
                elif cron_id:
                    try:
                        cron_id.sudo().write({'nextcall': datetime.now() + timedelta(minutes=5)})
                    except Exception as e:
                        _logger.debug("Get Feed Submission Method %s will be called after commit", e)

    def get_amz_message_information_ept(self, amazon_orders):
        """
        Find done pickings also find pickings location destination is customer,
        then prepare xml details to update in amazon feed
        :param amazon_orders: sale.order()
        :return: message_information, shipment_pickings
        @author: Keyur Kanani
        """
        shipment_pickings = []
        message_information = ''
        message_id = 1
        for amazon_order in amazon_orders:
            for picking in amazon_order.picking_ids:
                #Here We Take only done picking and updated in amazon false
                if (picking.updated_in_amazon and amazon_order.picking_ids.filtered(
                        lambda l:l.backorder_id.id==picking.id)) or picking.state != 'done' or \
                        picking.location_dest_id.usage != 'customer':
                    continue
                if not amazon_order.amz_shipment_service_level_category:
                    continue
                fulfillment_date_concat = self.get_shipment_fulfillment_date(picking)
                shipment_pickings.append(picking.id)
                manage_multi_tracking_number_in_delivery_order = False if picking.carrier_tracking_ref else True
                if not manage_multi_tracking_number_in_delivery_order:
                    ship_info = ''
                    carrier_name = self.amz_get_carrier_name_ept(picking)
                    tracking_no = picking.carrier_tracking_ref
                    parcel = self.amz_prepare_parcel_values_ept(carrier_name, tracking_no, amazon_order, fulfillment_date_concat)
                    partner = amazon_order.warehouse_id.partner_id
                    if partner:
                        ship_info = self.amz_get_ship_from_address_details(partner)
                    message_information += self.create_parcel_for_single_tracking_number(parcel, message_id, ship_info)
                    message_id = message_id + 1
                else:
                    #Create message for bom type products
                    phantom_msg_info, message_id, update_move_ids = self.get_qty_for_phantom_type_products(
                        amazon_order, picking, message_id, fulfillment_date_concat)
                    if phantom_msg_info:
                        message_information += phantom_msg_info
                    # Create Message for each move
                    message_information, message_id = self.create_message_for_multi_tracking_number_ept(
                        picking, message_information, update_move_ids, message_id)
        return message_information, shipment_pickings

    @staticmethod
    def amz_get_ship_from_address_details(partner):
        """
        Prepare xml data for ship from address in the update tracking numbers
        :param partner:res.partner()
        :return: text
        @author: Keyur Kanani
        """
        address =""
        if partner.street:
            address = """<AddressFieldOne>%s</AddressFieldOne>""" % partner.street
        if partner.street2:
            address += """<AddressFieldTwo>%s</AddressFieldTwo>""" %  partner.street2
        ship_from = """<ShipFromAddress>
            <Name>%s</Name>
            %s
            <City>%s</City>
            <County>%s</County>
            <StateOrRegion>%s</StateOrRegion>
            <PostalCode>%s</PostalCode>
            <CountryCode>%s</CountryCode>
        </ShipFromAddress>""" % (partner.name, address, partner.city,
                                 partner.country_id.name if partner.country_id else '',
                                 partner.state_id.code if partner.state_id else '', partner.zip,
                                 partner.country_id.code if partner.country_id else '')

        return ship_from

    def create_message_for_multi_tracking_number_ept(self, picking, message_information, update_move_ids, message_id):
        """
        Prepare message for multiple tracking number pickings
        :param picking: stock.move()
        :param message_information: string
        :param update_move_ids: list[]
        :param message_id: int
        :return: message_information, message_id
        @author: Keyur Kanani
        """
        fulfillment_date_concat = self.get_shipment_fulfillment_date(picking)
        carrier_name = self.amz_get_carrier_name_ept(picking)
        for move in picking.move_lines:
            if move in update_move_ids or move.sale_line_id.product_id.id != move.product_id.id:
                continue
            amazon_order_item_id = move.sale_line_id.amazon_order_item_id
            # Create Package for the each parcel
            tracking_no_with_qty = {}
            for move_line in move.move_line_ids:
                if move_line.qty_done < 0.0:
                    continue
                tracking_no = move_line.result_package_id and move_line.result_package_id.tracking_no or 'UNKNOWN'
                quantity = tracking_no_with_qty.get(tracking_no, 0.0)
                quantity = quantity + move_line.qty_done
                tracking_no_with_qty.update({tracking_no: quantity})
            for tracking_no, product_qty in tracking_no_with_qty.items():
                tracking_no = '' if tracking_no == 'UNKNOWN' else tracking_no
                product_qty = self.amz_get_sale_line_product_qty_ept(move.sale_line_id)
                parcel = self.amz_prepare_parcel_values_ept(carrier_name, tracking_no, picking.sale_id,
                                                            fulfillment_date_concat)
                parcel.update({'qty': product_qty, 'amazon_order_item_id': amazon_order_item_id})
                message_information += self.create_parcel_for_multi_tracking_number(parcel, message_id, picking.sale_id)
                message_id = message_id + 1
        return message_information, message_id

    @staticmethod
    def amz_prepare_parcel_values_ept(carrier_name, tracking_no, amazon_order, fulfillment_date_concat):
        """
        Prepare courier parcel values
        :param carrier_name: carrier name
        :param tracking_no: shipment tracking number
        :param amazon_order: sale.order()
        :return: dict{}
        @author: Keyur Kanani
        """
        shipment_service_level_category = amazon_order.picking_ids.mapped('carrier_id.fbm_shipping_method') and amazon_order.picking_ids.mapped('carrier_id.fbm_shipping_method')[0] or amazon_order.picking_ids.mapped('carrier_id.amz_shipping_service_level_category') and amazon_order.picking_ids.mapped('carrier_id.amz_shipping_service_level_category')[0] or amazon_order.amz_shipment_service_level_category
        return {'tracking_no': tracking_no or '', 'order_ref': amazon_order.amz_order_reference,
                'carrier_name': carrier_name or '',
                'shipping_level_category': shipment_service_level_category,
                'fulfillment_date_concat': fulfillment_date_concat or False}

    @staticmethod
    def get_shipment_fulfillment_date(picking):
        """
        prepare fulfillment data from shipment
        :param picking: stock.move()
        :return: date string
        @author: Keyur Kanani
        """
        if picking.date_done:
            fulfillment_date = time.strptime(str(picking.date_done), "%Y-%m-%d %H:%M:%S")
            fulfillment_date = time.strftime("%Y-%m-%dT%H:%M:%S", fulfillment_date)
        else:
            fulfillment_date = time.strftime('%Y-%m-%dT%H:%M:%S')
        return str(fulfillment_date) + '-00:00'

    @staticmethod
    def amz_get_carrier_name_ept(picking):
        """
        Get carrier name from picking
        :param picking: stock.move()
        :return: string
        @author: Keyur Kanani
        """
        if picking.carrier_id and picking.carrier_id.amz_carrier_code:
            carrier_name = picking.carrier_id.amz_carrier_code
        else:
            carrier_name =picking.carrier_id.name
        return carrier_name

    def amz_prepare_phantom_product_dict_ept(self, picking_ids):
        """
        Prepare phantom product dictionary from picking ids
        :param picking_ids: list
        :return: dict{}
        @author: Keyur Kanani
        """
        move_obj = self.env['stock.move']
        moves = move_obj.search(
            [('picking_id', 'in', picking_ids), ('picking_type_id.code', '!=', 'incoming'),
             ('state', 'not in', ['draft', 'cancel']), ('updated_in_amazon', '=', False)])
        phantom_product_dict = {}
        for move in moves:
            if move.sale_line_id.product_id.id != move.product_id.id:
                if move.sale_line_id in phantom_product_dict and move.product_id.id not in phantom_product_dict.get(
                        move.sale_line_id):
                    phantom_product_dict.get(move.sale_line_id).append(move.product_id.id)
                else:
                    phantom_product_dict.update({move.sale_line_id: [move.product_id.id]})
        return phantom_product_dict

    def get_qty_for_phantom_type_products(self, order, picking, message_id, fulfillment_date_concat):
        """
        Get quantity of phantom type products and prepare message information
        :param order: sale.order()
        :param picking: stock.move()
        :param message_id: int
        :param fulfillment_date_concat: date
        :return: message_information, message_id, update_move_ids
        @author: Keyur Kanani
        """
        message_information = ''
        move_obj = self.env['stock.move']
        update_move_ids = []
        picking_ids = order.picking_ids.ids
        phantom_product_dict = self.amz_prepare_phantom_product_dict_ept(picking_ids)
        for sale_line_id, product_ids in phantom_product_dict.items():
            moves = move_obj.search([('picking_id', 'in', picking_ids), ('state', 'in', ['draft', 'cancel']),
                                     ('product_id', 'in', product_ids)])
            if not moves:
                moves = move_obj.search([('picking_id', 'in', picking_ids), ('state', '=', 'done'),
                                         ('product_id', 'in', product_ids), ('updated_in_amazon', '=', False)])
                tracking_no = picking.carrier_tracking_ref
                for move in moves:
                    if not tracking_no:
                        for move_line in move.move_line_ids:
                            tracking_no = move_line.result_package_id and \
                                          move_line.result_package_id.tracking_no or False
                update_move_ids += moves.ids
                product_qty = self.amz_get_sale_line_product_qty_ept(sale_line_id)
                carrier_name = self.amz_get_carrier_name_ept(picking)
                parcel = self.amz_prepare_parcel_values_ept(carrier_name, tracking_no, order, fulfillment_date_concat)
                parcel.update({'qty': product_qty, 'amazon_order_item_id': sale_line_id.amazon_order_item_id})
                message_information += self.create_parcel_for_multi_tracking_number(parcel, message_id, order)
                message_id = message_id + 1
        return message_information, message_id, update_move_ids

    @staticmethod
    def amz_get_sale_line_product_qty_ept(sale_line_id):
        """
        Divide product quantity with asin quantity if asin qty is available in product
        :param sale_line_id: sale.order.line()
        :return: int
        @author: Keyur Kanani
        """
        product_qty = sale_line_id.product_qty
        if sale_line_id and sale_line_id.amazon_product_id and \
                sale_line_id.amazon_product_id.allow_package_qty:
            asin_qty = sale_line_id.amazon_product_id.asin_qty
            if asin_qty != 0:
                product_qty = product_qty / asin_qty
        return int(product_qty)

    @staticmethod
    def create_data(message_information, merchant_id):
        """
        Prepare xml header data for send in amazon feed.
        :param message_information: text
        :param merchant_id: int
        :return: text
        @author: Keyur Kanani
        """
        data = """<?xml version="1.0" encoding="utf-8"?>
                        <AmazonEnvelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="amzn-envelope.xsd">
                            <Header>
                                <DocumentVersion>1.01</DocumentVersion>
                                    <MerchantIdentifier>%s</MerchantIdentifier>
                            </Header>
                        <MessageType>OrderFulfillment</MessageType>""" % (merchant_id) + message_information + """
                        </AmazonEnvelope>"""
        return data

    @staticmethod
    def create_parcel_for_single_tracking_number(parcel, message_id, ship_info):
        """
        Prepare Parcel tracking information data for single tracking number in picking
        :param parcel: dict{}
        :param message_id: int
        :return: text
        @author: Keyur Kanani
        """
        message_information = ''
        if parcel.get('carrier_code'):
            carrier_information = '''<CarrierCode>%s</CarrierCode>''' % (parcel.get('carrier_code'))
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
        """
        Prepare Parcel tracking information for multiple tracking numbers of a picking
        :param parcel: dict{}
        :param message_id: int
        :return: text
        @author: Keyur Kanani
        """
        message_information = ''
        ship_info = ""
        partner = order.warehouse_id.partner_id
        if partner:
            ship_info = self.amz_get_ship_from_address_details(partner)
        if parcel.get('carrier_code'):
            carrier_information = '''<CarrierCode>%s</CarrierCode>''' % (parcel.get('carrier_code'))
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

    def get_amazon_tax_registration_details(self, order):
        """
        Find Out VAT Numbers from OrderItem Response.
        :param order: dict{}
        :return: vat, vat_country_code
        """
        module_obj = self.env['ir.module.module']
        vat_module = module_obj.sudo().search([('name', '=', 'base_vat'), ('state', '=', 'installed')])
        vat = ''
        vat_country_code = order.get('ShippingAddress', {}).get('CountryCode', {}).get('value', '') if order.get(
                'ShippingAddress', {}).get('CountryCode', '') else ''
        if order.get('BuyerEmail', {}).get('value'):
            tax_registration_details = order.get('TaxRegistrationDetails', {}).get('member', {})
            if tax_registration_details:
                order.update({'check_vat_ept':True if vat_module else False})
                if isinstance(tax_registration_details, list):
                    for tax_registration_val in tax_registration_details:
                        if vat_country_code == tax_registration_val.get(
                                'taxRegistrationAuthority', {}).get('country', {}).get('value', ''):
                            vat = tax_registration_val.get('taxRegistrationId', {}).get('value', '')
                else:
                    vat = tax_registration_details.get('taxRegistrationId', {}).get('value', '')
                    vat_country_code = tax_registration_details.get('taxRegistrationAuthority', {}).get(
                            'country', {}).get('value', '')
            else:
                # Not tested because of not getting in live response changes based on api response
                buyer_tax_info = order.get('BuyerTaxInfo', {})
                if buyer_tax_info:
                    order.update({'check_vat_ept':True if vat_module else False})
                buyer_tax_details = buyer_tax_info.get('TaxClassifications', {})
                vat = buyer_tax_details.get('TaxClassification', {}).get('Value', {}).get('value', '')
                vat_country_code = buyer_tax_info.get('TaxingRegion', {}).get('value', '')

        return vat, vat_country_code
