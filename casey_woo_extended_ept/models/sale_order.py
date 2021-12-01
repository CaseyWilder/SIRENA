# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.
import logging

from odoo import models, api
from odoo.tools.misc import split_every

_logger = logging.getLogger("WooCommerce")


class SaleOrder(models.Model):
    _inherit = "sale.order"

    @api.model
    def update_woo_order_status(self, woo_instance):
        """
        Override to this functionality for export tracking provider, tracking no and tracking date
        Override by: Meera Sidapara on date 02/11/2021
        Task Id: 179523
        """
        common_log_book_obj = self.env["common.log.book.ept"]
        instance_obj = self.env["woo.instance.ept"]
        log_lines = []
        woo_order_ids = []
        if isinstance(woo_instance, int):
            woo_instance = instance_obj.browse(woo_instance)
        wc_api = woo_instance.woo_connect()
        sales_orders = self.search([("warehouse_id", "=", woo_instance.woo_warehouse_id.id),
                                    ("woo_order_id", "!=", False), ("woo_instance_id", "=", woo_instance.id),
                                    ("state", "=", "sale"), ("woo_status", "!=", 'completed')])

        for sale_order in sales_orders:
            if sale_order.updated_in_woo:
                continue

            pickings = sale_order.picking_ids.filtered(
                lambda x: x.location_dest_id.usage == "customer" and x.state != "cancel"
                          and not x.updated_in_woo)
            _logger.info("Start Order update status for Order : %s", sale_order.name)

            if all(state == 'done' for state in pickings.mapped("state")):
                # prepare tracking data for shipment
                tracking_data = []
                for picking_id in pickings.filtered(
                        lambda x: x.state == "done"):
                    if picking_id.carrier_id.delivery_type and picking_id.carrier_tracking_ref:
                        tracking_data.append({'tracking_provider': picking_id.delivery_carrier_id.delivery_type,
                                              'tracking_number': picking_id.carrier_tracking_ref,
                                              'date_shipped': str(picking_id.date_done)})
                if tracking_data:
                    woo_order_ids.append({"id": int(sale_order.woo_order_id), "status": "completed", "meta_data": [{
                        'key': '_wc_shipment_tracking_items', 'value': tracking_data
                    }]})
            elif not pickings and sale_order.state == "sale":
                woo_order_ids.append({"id": int(sale_order.woo_order_id), "status": "completed"})
                """When all products are service type."""
            else:
                continue

        for woo_orders in split_every(100, woo_order_ids):
            log_line_id = self.update_order_status_in_batch(woo_orders, wc_api, woo_instance)
            if log_line_id:
                if isinstance(log_line_id, list):
                    log_lines += log_line_id
                else:
                    log_lines.append(log_line_id)
            self._cr.commit()

        if log_lines:
            common_log_book_obj.woo_create_log_book('export', woo_instance, log_lines)
        return True
