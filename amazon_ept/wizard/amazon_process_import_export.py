# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.

"""
Added to perform the amazon import, export operations and added onchange and methods
to process for different amazon operations.
"""

import base64
import csv
import time
from collections import defaultdict
from datetime import datetime, timedelta
from io import StringIO
import os

from odoo import models, fields, api, _
from odoo.addons.iap.tools import iap_tools
from odoo.exceptions import UserError, ValidationError

from ..endpoint import DEFAULT_ENDPOINT


class AmazonProcessImportExport(models.TransientModel):
    """
    Added class to perform amazon import and export operations.
    """
    _name = 'amazon.process.import.export'
    _description = 'Amazon Import Export Process'

    seller_id = fields.Many2one('amazon.seller.ept', string='Amazon Seller',
                                help="Select Amazon Seller Account")

    amazon_program = fields.Selection(related="seller_id.amazon_program")

    us_amazon_program = fields.Selection(related="seller_id.amz_fba_us_program")
    instance_id = fields.Many2one('amazon.instance.ept', string='Instance',
                                  help="This Field relocates amazon instance.")
    order_removal_instance_id = fields.Many2one('amazon.instance.ept', string='Removal Instance',
                                                help="This instance is used for the Removal order.")
    is_another_soft_create_fba_inventory = fields.Boolean(
        related="seller_id.is_another_soft_create_fba_inventory",
        string="Does another software create the FBA Inventory reports?",
        help="Does another software create the FBA Inventory reports")
    instance_ids = fields.Many2many("amazon.instance.ept", 'amazon_instance_import_export_rel',
                                    'process_id', 'instance_id', "Instances",
                                    help="Select Amazon Marketplaces where you want to perform "
                                         "opetations.")
    list_settlement_report = fields.Boolean("List settlement report?")
    report_start_date = fields.Datetime("Start Date", help="Start date of report.")
    report_end_date = fields.Datetime("End Date", help="End date of report.")
    selling_on = fields.Selection([
        ('FBM', 'FBM'),
        ('FBA', 'FBA'),
        ('fba_fbm', 'FBA & FBM')
    ], 'Operation For')
    operations = fields.Selection([
        ('Export_Stock_From_Odoo_To_Amazon', 'Export Stock from Odoo to Amazon'),
        ('Update_Track_Number_And_Ship_Status', 'Update Tracking Number & Shipment Status'),
        ('Check_Cancel_Orders_FBM', 'Check Cancel Orders'),
        ('Import_FBM_Shipped_Orders', 'Import FBM Shipped Orders'),
        ('Import_Missing_Unshipped_Orders', 'Import Missing UnShipped Orders'),
        ('Import_Unshipped_Orders', 'Import Unshipped Orders')
    ], 'FBM Operations')
    fba_operations = fields.Selection([
        ('Import_Pending_Orders', 'Import Pending Orders'),
        ('Check_Cancel_Orders_FBA', 'Check Cancel Orders'),
        ('Shipment_Report', 'Shipment Report'),
        ('Stock_Adjustment_Report', 'Stock Adjustment Report'),
        ('Removal_Order_Report', 'Removal Order Report'),
        ('Customer_Return_Report', 'Customer Return Report'),
        ('removal_order_request', 'Removal Order Request'),
        ('Import Inbound Shipment', 'Import Inbound Shipment'),
        ('Create_Inbound_Shipment_Plan', 'Create Inbound Shipment Plan'),
        ('fba_live_inventory_report', 'FBA Live Inventory')
    ], 'Operations')

    both_operations = fields.Selection([
        ('Import_Product', 'Map Product'),
        ('Sync_Active_Products', 'Sync Active Products'),
        ('Export_Price_From_Odoo_To_Amazon', 'Export Price From Odoo to Amazon'),
        ('List_Settlement_Report', 'List Settlement report'),
        ('request_rating_report', 'Request Rating Report'),
        ('vcs_tax_report', 'VCS Tax Report')
    ], 'FBA & FBM Operations')
    is_vcs_enabled = fields.Boolean('Is VCS Report Enabled ?', default=False, store=False)
    is_split_report = fields.Boolean('Is Split Report ?', default=False)
    split_report_by_days = fields.Selection([
        ('3', '3'),
        ('7', '7'),
        ('15', '15')
    ])
    fbm_order_updated_after_date = fields.Datetime('Updates After')
    import_fba_pending_sale_order = fields.Boolean('Sale order(Only Pending Orders)',
                                                   help="System will import pending FBA orders "
                                                        "from Amazon")
    check_order_status = fields.Boolean("Check Cancelled Order in Amazon",
                                        help="If ticked, system will check the orders status in "
                                             "canceled in Amazon, then system will cancel that "
                                             "order "
                                             "is Odoo too.")
    export_inventory = fields.Boolean()
    export_product_price = fields.Boolean('Update Product Price')
    updated_after_date = fields.Datetime('Updated After')
    shipment_id = fields.Char()
    from_warehouse_id = fields.Many2one('stock.warehouse', string="From Warehouse")
    update_price_in_pricelist = fields.Boolean(string='Update price in pricelist?', default=False,
                                               help='Update or create product line in pricelist '
                                                    'if ticked.')
    auto_create_product = fields.Boolean(string='Auto create product?', default=False,
                                         help='Create product in ERP if not found.')
    file_name = fields.Char(string='Name')
    choose_file = fields.Binary(string="Select File")
    delimiter = fields.Selection([('tab', 'Tab'), ('semicolon', 'Semicolon'), ('comma', 'Comma')],
                                 string="Separator", default='comma')
    user_warning = fields.Text(string="Note: ", store=False)
    pan_eu_instance_id = fields.Many2one('amazon.instance.ept', string='Instance(UK)',
                                         help="This Field relocates amazon UK instance.")
    us_region_instance_id = fields.Many2one('amazon.instance.ept', string='Instance(US)',
                                            help="This Field relocates amazon North America Region instance.")
    country_code = fields.Char(related='seller_id.country_id.code', string='Country Code')
    mci_efn_instance_id = fields.Many2one('amazon.instance.ept', string='Instance(EU)',
                                          help="This Field relocates amazon MCI or MCI+EFN instance.")

    @api.onchange('report_start_date', 'report_end_date')
    def onchange_shipment_report_date(self):
        """
        Added onchange to allow option to split report based on selected date range difference is
        more than 7 days.
        """
        if self.report_start_date and self.report_end_date:
            count = self.report_end_date.date() - self.report_start_date.date()
            if count.days > 7 and not self.seller_id.is_another_soft_create_fba_shipment:
                self.is_split_report = True
            else:
                self.is_split_report = False

    @api.onchange('selling_on')
    def onchange_selling_on(self):
        """
        Added set operations vals false based on selling on.
        """
        self.operations = False
        self.fba_operations = False
        self.both_operations = False

    @api.onchange('operations')
    def onchange_operations(self):
        """
        On change of operations field it will check the active scheduler or scheduler
        exist then it's next run time.
        """
        self.export_inventory = False
        self.export_product_price = False
        self.list_settlement_report = False
        self.fbm_order_updated_after_date = False
        self.updated_after_date = False
        self.report_start_date = False
        self.report_end_date = False

        self.user_warning = None
        if self.operations == "Export_Stock_From_Odoo_To_Amazon":
            self.check_running_schedulers('ir_cron_auto_export_inventory_seller_')

        if self.operations == "Update_Track_Number_And_Ship_Status":
            self.check_running_schedulers('ir_cron_auto_update_order_status_seller_')

        if self.operations == "Check_Cancel_Orders_FBM":
            self.check_running_schedulers('ir_cron_auto_check_canceled_fbm_order_in_amazon_seller_')

        if self.operations == "Import_Unshipped_Orders":
            self.check_running_schedulers('ir_cron_import_amazon_orders_seller_')

    @api.onchange('fba_operations')
    def onchange_fba_operations(self):
        """
        On change of fba_operations field it set start and end date as per configurations from
        seller
        default start date is -3 days from the date.
        @author: Keyur Kanani
        :return:
        """
        self.user_warning = None
        if self.fba_operations == "Shipment_Report":
            self.report_start_date = datetime.now() - timedelta(self.seller_id.shipping_report_days)
            self.report_end_date = datetime.now()
            self.check_running_schedulers('ir_cron_import_amazon_fba_shipment_report_seller_')

        if self.fba_operations == "Customer_Return_Report":
            self.report_start_date = datetime.now() - timedelta(
                self.seller_id.customer_return_report_days)
            self.report_end_date = datetime.now()
            self.check_running_schedulers('ir_cron_auto_import_customer_return_report_seller_')

        if self.fba_operations == "Stock_Adjustment_Report":
            self.report_start_date = datetime.now() - timedelta(
                self.seller_id.inv_adjustment_report_days)
            self.report_end_date = datetime.now()
            self.check_running_schedulers('ir_cron_create_fba_stock_adjustment_report_seller_')

        if self.fba_operations == "Removal_Order_Report":
            self.report_start_date = datetime.now() - timedelta(
                self.seller_id.removal_order_report_days)
            self.report_end_date = datetime.now()
            self.check_running_schedulers('ir_cron_create_fba_removal_order_report_seller_')

        if self.fba_operations == "fba_live_inventory_report":
            self.report_start_date = datetime.now() - timedelta(
                self.seller_id.live_inv_adjustment_report_days)
            self.report_end_date = datetime.now()
            self.check_running_schedulers('ir_cron_import_stock_from_amazon_fba_live_report_')

        if self.fba_operations == "Import_Pending_Orders":
            self.check_running_schedulers('ir_cron_import_amazon_fba_pending_order_seller_')

        if self.fba_operations == "Import Inbound Shipment":
            self.check_running_schedulers('ir_cron_inbound_shipment_check_status_')

    @api.onchange('both_operations')
    def onchange_both_operations(self):
        """
        On change of fba_fbm_operations field it will check the active scheduler or scheduler
        exist then it's next run time.
        @author: Keyur Kanani
        :return:
        """
        self.user_warning = None
        if self.both_operations == "List_Settlement_Report":
            self.check_running_schedulers('ir_cron_auto_import_settlement_report_seller_')
        if self.both_operations == "request_rating_report":
            self.report_start_date = datetime.now() - timedelta(self.seller_id.rating_report_days)
            self.report_end_date = datetime.now()
            self.check_running_schedulers('ir_cron_rating_request_report_seller_')
        if self.both_operations == "vcs_tax_report":
            self.report_start_date = datetime.now() - timedelta(self.seller_id.fba_vcs_report_days)
            self.report_end_date = datetime.now()
            self.check_running_schedulers('ir_cron_auto_import_vcs_tax_report_seller_')

    def check_running_schedulers(self, cron_xml_id):
        """
        use: 1. If scheduler is running for ron_xml_id + seller_id, then this function will
        notify user that
                the process they are doing will be running in the scheduler.
                if they will do this process then the result cause duplicate.
            2. Also if scheduler is in progress in backend then the execution will give UserError
            Popup
                and terminates the process until scheduler job is done.
        :param cron_xml_id: string[cron xml id]
        :return:
        """
        cron_id = self.env.ref('amazon_ept.%s%d' % (cron_xml_id, self.seller_id.id),
                               raise_if_not_found=False)
        if cron_id and cron_id.sudo().active:
            res = cron_id.try_cron_lock()
            if self._context.get('raise_warning') and res and res.get('reason'):
                raise UserError(_("You are not allowed to run this Action. \n"
                                  "The Scheduler is already started the Process of Importing "
                                  "Orders."))
            if res and res.get('result'):
                self.user_warning = "This process is executed through scheduler also, " \
                                    "Next Scheduler for this process will run in %s Minutes" \
                                    % res.get('result')
            elif res and res.get('reason'):
                self.user_warning = res.get('reason')

    def import_export_processes(self):
        """
        Import / Export Operations are managed from here.
        as per selection on wizard this function will execute

        Updated by : twinkalc on 7th jan 2021
        Updated code to process for inv report for UK or Pan Eu.
        :return: True
        """
        sale_order_obj = self.env['sale.order']
        fbm_sale_order_report_obj = self.env['fbm.sale.order.report.ept']
        fba_shipping_report_obj = self.env['shipping.report.request.history']
        customer_return_report_obj = self.env['sale.order.return.report']
        amazon_product_obj = self.env['amazon.product.ept']
        stock_adjustment_report_obj = self.env['amazon.stock.adjustment.report.history']
        removal_order_request_report_record = self.env['amazon.removal.order.report.history']
        live_inventory_request_report_record = self.env['amazon.fba.live.stock.report.ept']
        amazon_removal_order_obj = self.env['amazon.removal.order.ept']
        import_shipment_obj = self.env['amazon.inbound.import.shipment.ept']
        rating_report_obj = self.env['rating.report.history']
        vcs_tax_report_obj = self.env['amazon.vcs.tax.report.ept']
        seller_pending_order_marketplaces = defaultdict(list)
        cancel_order_marketplaces = defaultdict(list)
        cancel_order_marketplaces_fbm = defaultdict(list)
        seller_stock_instance = defaultdict(list)
        export_product_price_instance = defaultdict(list)

        if self.both_operations == "List_Settlement_Report":
            self.with_context({'raise_warning': True}).check_running_schedulers(
                'ir_cron_auto_import_settlement_report_seller_')
            vals = {'report_type': '_GET_V2_SETTLEMENT_REPORT_DATA_FLAT_FILE_V2_',
                    'name': 'Amazon Settlement Reports',
                    'model_obj': self.env['settlement.report.ept'],
                    'sequence': self.env.ref('amazon_ept.seq_import_settlement_report_job'),
                    'tree_id': self.env.ref('amazon_ept.amazon_settlement_report_tree_view_ept'),
                    'form_id': self.env.ref('amazon_ept.amazon_settlement_report_form_view_ept'),
                    'res_model': 'settlement.report.ept',
                    'start_date': self.report_start_date,
                    'end_date': self.report_end_date
                    }
            return self.get_reports(vals)
        if self.both_operations == "request_rating_report":
            self.with_context({'raise_warning': True}).check_running_schedulers(
                'ir_cron_rating_request_report_seller_')
            if not self.report_start_date or not self.report_end_date:
                raise UserError(_('Please select Date Range.'))

            rating_report_record = rating_report_obj.create({
                'seller_id': self.seller_id.id,
                'start_date': self.report_start_date,
                'end_date': self.report_end_date
            })
            return {
                'name': _('Rating Report Request History'),
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'rating.report.history',
                'type': 'ir.actions.act_window',
                'res_id': rating_report_record.id
            }
        if self.operations == 'Update_Track_Number_And_Ship_Status':
            self.with_context({'raise_warning': True}).check_running_schedulers(
                'ir_cron_auto_update_order_status_seller_')
            return sale_order_obj.amz_update_tracking_number(self.seller_id)

        if self.operations == 'Import_FBM_Shipped_Orders':
            return sale_order_obj.import_fbm_shipped_or_missing_unshipped_orders(self.seller_id, self.instance_ids,
                                                                                 self.fbm_order_updated_after_date, ['Shipped'])
        if self.operations == 'Import_Missing_Unshipped_Orders':
            return sale_order_obj.import_fbm_shipped_or_missing_unshipped_orders(self.seller_id, self.instance_ids,
                                                                                 self.fbm_order_updated_after_date,
                                                                                 ['Unshipped', 'PartiallyShipped'])


        if self.operations == "Import_Unshipped_Orders":
            self.with_context({'raise_warning': True}).check_running_schedulers(
                'ir_cron_import_amazon_orders_seller_')
            record = fbm_sale_order_report_obj.create({
                'seller_id': self.seller_id.id,
                'report_type': '_GET_FLAT_FILE_ORDER_REPORT_DATA_',
            })
            record.request_report()
            return {
                'name': _('FBM Sale Order'),
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'fbm.sale.order.report.ept',
                'type': 'ir.actions.act_window',
                'res_id': record.id
            }
        if self.fba_operations == "Shipment_Report":
            self.with_context({'raise_warning': True}).check_running_schedulers(
                'ir_cron_import_amazon_fba_shipment_report_seller_')
            if not self.report_start_date or not self.report_end_date:
                raise UserError(_('Please select Date Range.'))
            if self.seller_id.is_another_soft_create_fba_shipment:
                vals = {'report_type': '_GET_AMAZON_FULFILLED_SHIPMENTS_DATA_',
                        'name': 'FBA Shipping Report',
                        'model_obj': self.env['shipping.report.request.history'],
                        'sequence': self.env.ref('amazon_ept.seq_import_shipping_report_job'),
                        'tree_id': self.env.ref(
                            'amazon_ept.amazon_shipping_report_request_history_tree_view_ept'),
                        'form_id': self.env.ref(
                            'amazon_ept.amazon_shipping_report_request_history_form_view_ept'),
                        'res_model': 'shipping.report.request.history',
                        'start_date': self.report_start_date,
                        'end_date': self.report_end_date
                        }
                self.get_reports(vals)
            elif self.is_split_report and not self.split_report_by_days:
                raise UserError(_('Please select the Split Report By Days.'))
            elif self.is_split_report and self.split_report_by_days:
                start_date = self.report_start_date
                end_date = False
                shipping_report_record_list = []

                while start_date <= self.report_end_date:
                    if end_date:
                        start_date = end_date

                    if start_date >= self.report_end_date:
                        break

                    end_date = (start_date + timedelta(int(self.split_report_by_days))) - timedelta(
                        1)
                    if end_date > self.report_end_date:
                        end_date = self.report_end_date

                    shipping_report_record = fba_shipping_report_obj.create({
                        'seller_id': self.seller_id.id,
                        'start_date': start_date,
                        'end_date': end_date
                    })
                    shipping_report_record.request_report()
                    shipping_report_record_list.append(shipping_report_record.id)

                return {
                    'name': _('FBA Shipping Report'),
                    'view_mode': 'tree, form',
                    'views': [
                        (self.env.ref(
                            'amazon_ept.amazon_shipping_report_request_history_tree_view_ept').id,
                         'tree'),
                        (False, 'form')],
                    'res_model': 'shipping.report.request.history',
                    'type': 'ir.actions.act_window',
                    'res_id': shipping_report_record_list
                }
            else:
                shipping_report_record = fba_shipping_report_obj.create({
                    'seller_id': self.seller_id.id,
                    'start_date': self.report_start_date,
                    'end_date': self.report_end_date
                })
                shipping_report_record.request_report()
                return {
                    'name': _('FBA Shipping Report'),
                    'view_mode': 'form',
                    'res_model': 'shipping.report.request.history',
                    'type': 'ir.actions.act_window',
                    'res_id': shipping_report_record.id
                }
        if self.fba_operations == 'Customer_Return_Report':
            self.with_context({'raise_warning': True}).check_running_schedulers(
                'ir_cron_auto_import_customer_return_report_seller_')
            customer_return_report_record = customer_return_report_obj.create({
                'seller_id': self.seller_id.id,
                'start_date': self.report_start_date,
                'end_date': self.report_end_date
            })
            customer_return_report_record.request_customer_return_report()
            return {
                'name': _('Customer Return Report'),
                'view_mode': 'form',
                'res_model': 'sale.order.return.report',
                'type': 'ir.actions.act_window',
                'res_id': customer_return_report_record.id
            }
        if self.fba_operations == "Stock_Adjustment_Report":
            self.with_context({'raise_warning': True}).check_running_schedulers(
                'ir_cron_create_fba_stock_adjustment_report_seller_')
            if not self.report_start_date or not self.report_end_date:
                raise UserError(_('Please select Date Range.'))

            stock_adjustment_report_record = stock_adjustment_report_obj.create({
                'seller_id': self.seller_id.id,
                'start_date': self.report_start_date,
                'end_date': self.report_end_date
            })
            return {
                'name': _('Stock Adjustment Report Request History'),
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'amazon.stock.adjustment.report.history',
                'type': 'ir.actions.act_window',
                'res_id': stock_adjustment_report_record.id
            }

        if self.fba_operations == 'fba_live_inventory_report':
            self.with_context({'raise_warning': True}).check_running_schedulers(
                'ir_cron_import_stock_from_amazon_fba_live_report_')

            if self.seller_id.is_another_soft_create_fba_inventory:
                if not self.report_start_date or not self.report_end_date:
                    raise UserError(_('Please select Date Range.'))
                vals = {'start_date': self.report_start_date,
                        'end_date': self.report_end_date,
                        'seller_id': self.seller_id,
                        'us_region_instance_id': self.us_region_instance_id or self.mci_efn_instance_id or self.pan_eu_instance_id or False
                        }
                fba_live_stock_report = live_inventory_request_report_record.get_inventory_report(
                    vals)
                return fba_live_stock_report

            if self.amazon_program in ('pan_eu', 'cep'):
                instance_id = self.pan_eu_instance_id
                report_type = '_GET_FBA_MYI_UNSUPPRESSED_INVENTORY_DATA_'
                if instance_id:
                    fba_live_stock_report_ids = self.with_context(
                        instance_ids=instance_id).create_and_request_amazon_live_inv_report_ids(report_type, False,
                                                                                                False, False)
                else:
                    fba_live_stock_report_ids = self.create_and_request_amazon_live_inv_report_ids(report_type, False,
                                                                                                   False, False)

            elif not self.seller_id.is_european_region and not self.seller_id.amz_fba_us_program == 'narf':
                report_type = '_GET_FBA_MYI_UNSUPPRESSED_INVENTORY_DATA_'
                fba_live_stock_report_ids = self.with_context(
                    {'instance_ids': self.us_region_instance_id if self.us_region_instance_id else self.seller_id.instance_ids}).create_and_request_amazon_live_inv_report_ids(
                    report_type, datetime.now(), False, False)

            elif self.amazon_program == 'efn' or self.seller_id.amz_fba_us_program == 'narf':
                start_date = (datetime.today().date() - timedelta(days=1)).strftime(
                    '%Y-%m-%d 00:00:00')
                end_date = (datetime.today().date() - timedelta(days=1)).strftime(
                    '%Y-%m-%d 23:59:59')
                report_type = '_GET_FBA_MYI_UNSUPPRESSED_INVENTORY_DATA_'
                fba_live_stock_report_ids = self.create_and_request_amazon_live_inv_report_ids(report_type, False,
                                                                                               start_date, end_date)
            elif self.amazon_program in ('mci', 'efn+mci'):
                start_date = (datetime.today().date() - timedelta(days=1)).strftime(
                    '%Y-%m-%d 00:00:00')
                end_date = (datetime.today().date() - timedelta(days=1)).strftime(
                    '%Y-%m-%d 23:59:59')
                report_type = '_GET_FBA_MYI_UNSUPPRESSED_INVENTORY_DATA_'
                fba_live_stock_report_ids = self.with_context(
                    {'instance_ids': self.mci_efn_instance_id if self.mci_efn_instance_id else
                     self.seller_id.instance_ids}).create_and_request_amazon_live_inv_report_ids(report_type, False,
                                                                                                 start_date, end_date)

            if len(fba_live_stock_report_ids) > 1:
                return {
                    'name': _('FBA Live Stock Report'),
                    'view_type': 'tree',
                    'view_mode': 'tree',
                    'res_model': 'amazon.fba.live.stock.report.ept',
                    'type': 'ir.actions.act_window',
                    'domain': [('id', 'in', fba_live_stock_report_ids)]
                }
            elif fba_live_stock_report_ids:
                return {
                    'name': _('FBA Live Stock Report'),
                    'view_type': 'form',
                    'view_mode': 'form',
                    'res_model': 'amazon.fba.live.stock.report.ept',
                    'type': 'ir.actions.act_window',
                    'res_id': fba_live_stock_report_ids[0]
                }

        if self.fba_operations == "Removal_Order_Report":
            self.with_context({'raise_warning': True}).check_running_schedulers(
                'ir_cron_create_fba_removal_order_report_seller_')
            if not self.report_start_date or not self.report_end_date:
                raise UserError(_('Please select Date Range.'))

            removal_order_request_report_record = removal_order_request_report_record.create({
                'seller_id': self.seller_id.id,
                'start_date': self.report_start_date,
                'end_date': self.report_end_date
            })
            return {
                'name': _('Removal Order Report Request History'),
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'amazon.removal.order.report.history',
                'type': 'ir.actions.act_window',
                'res_id': removal_order_request_report_record.id
            }
        if self.fba_operations == "removal_order_request":
            if not self.order_removal_instance_id or self.order_removal_instance_id and not \
                    self.order_removal_instance_id.is_allow_to_create_removal_order:
                raise UserError(_(
                    'This Seller no any instance configure removal order Please configure removal '
                    'order configuration.'))

            amazon_removal_order_obj = amazon_removal_order_obj.create({
                'removal_disposition': 'Return',
                'warehouse_id': self.order_removal_instance_id and
                                self.order_removal_instance_id.removal_warehouse_id.id or
                                False,
                'ship_address_id': self.order_removal_instance_id.company_id.partner_id.id,
                'company_id': self.seller_id.company_id.id,
                'instance_id': self.order_removal_instance_id.id,
            })
            return {
                'name': _('Removal Order Request'),
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'amazon.removal.order.ept',
                'type': 'ir.actions.act_window',
                'res_id': amazon_removal_order_obj.id
            }

        if self.fba_operations == "Import Inbound Shipment":
            self.with_context({'raise_warning': True}).check_running_schedulers(
                'ir_cron_inbound_shipment_check_status_')
            import_shipment_obj.get_inbound_import_shipment(self.instance_id,
                                                            self.from_warehouse_id,
                                                            self.shipment_id)

        if self.fba_operations == "Create_Inbound_Shipment_Plan":
            return self.wizard_create_inbound_shipment_plan(self.instance_id)

        if self.both_operations == 'vcs_tax_report':
            if not self.seller_id.is_vcs_activated:
                raise UserError( \
                    _("Please Select Invoice Upload Policy as per Seller Central Configurations."))
            self.with_context({'raise_warning': True}).check_running_schedulers(
                'ir_cron_auto_import_vcs_tax_report_seller_')

            vcs_report = vcs_tax_report_obj.create(
                {'report_type': '_SC_VAT_TAX_REPORT_',
                 'seller_id': self.seller_id.id,
                 'start_date': self.report_start_date,
                 'end_date': self.report_end_date,
                 'state': 'draft'
                 })
            vcs_report.request_report()
            self.seller_id.write({'vcs_report_last_sync_on': self.report_end_date})
            return {
                'name': _('Amazon VCS Tax Reports'),
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'amazon.vcs.tax.report.ept',
                'type': 'ir.actions.act_window',
                'res_id': vcs_report.id
            }

        if self.both_operations == "Sync_Active_Products":
            return self.create_sync_active_products(self.seller_id, self.instance_id,
                                                    self.update_price_in_pricelist,
                                                    self.auto_create_product)

        if self.both_operations == "Import_Product":
            return self.import_csv_file()

        if self.instance_ids:
            instance_ids = self.instance_ids
        else:
            instance_ids = self.seller_id.instance_ids

        for instance in instance_ids:
            if self.fba_operations == "Check_Cancel_Orders_FBA":
                cancel_order_marketplaces[instance.seller_id].append(instance.market_place_id)
            if self.operations == 'Check_Cancel_Orders_FBM':
                self.with_context({'raise_warning': True}).check_running_schedulers(
                    'ir_cron_auto_check_canceled_fbm_order_in_amazon_seller_')
                cancel_order_marketplaces_fbm[instance.seller_id].append(instance.market_place_id)
            if self.fba_operations == "Import_Pending_Orders":
                self.with_context({'raise_warning': True}).check_running_schedulers(
                    'ir_cron_import_amazon_fba_pending_order_seller_')
                seller_pending_order_marketplaces[instance.seller_id].append(
                    instance.market_place_id)
            if self.operations == 'Export_Stock_From_Odoo_To_Amazon':
                self.with_context({'raise_warning': True}).check_running_schedulers(
                    'ir_cron_auto_export_inventory_seller_')
                seller_stock_instance[instance.seller_id].append(instance)
            if self.both_operations == 'Export_Price_From_Odoo_To_Amazon':
                export_product_price_instance[instance.seller_id].append(instance)

        if cancel_order_marketplaces:
            for seller, marketplaces in cancel_order_marketplaces.items():
                sale_order_obj.cancel_amazon_fba_pending_sale_orders(seller,
                                                                     marketplaceids=marketplaces,
                                                                     instance_ids=instance_ids.ids or [])
        if cancel_order_marketplaces_fbm:
            for seller, marketplaces in cancel_order_marketplaces_fbm.items():
                sale_order_obj.cancel_amazon_fbm_pending_sale_orders(seller,
                                                                     marketplaceids=marketplaces, \
                                                                     instance_ids=instance_ids.ids or [])
        if seller_pending_order_marketplaces:
            for seller, marketplaces in seller_pending_order_marketplaces.items():
                sale_order_obj.import_fba_pending_sales_order(seller, marketplaces,
                                                              self.updated_after_date)

        if seller_stock_instance:
            for seller, instance_ids in seller_stock_instance.items():
                for instance in instance_ids:
                    instance.export_stock_levels()
        if export_product_price_instance:
            for seller, instance_ids in export_product_price_instance.items():
                for instance in instance_ids:
                    amazon_products = amazon_product_obj.search(
                        [('instance_id', '=', instance.id), ('exported_to_amazon', '=', True)])
                    if amazon_products:
                        amazon_products.update_price(instance)
        return True

    def create_and_request_amazon_live_inv_report_ids(self, report_type, report_date, start_date, \
                                                      end_date):
        """
        Added to request for FBA line inventory report.
        """
        ctx = self._context
        fba_live_stock_report_ids = []
        live_inventory_request_report_record = self.env['amazon.fba.live.stock.report.ept']
        fba_live_stock_report_vals = {'seller_id': self.seller_id.id,
                                      'report_type': report_type,
                                      'report_date': report_date,
                                      'start_date': start_date,
                                      'end_date': end_date}

        if ctx.get('instance_ids'):
            instance_ids = ctx.get('instance_ids')
            for instance in instance_ids:
                fba_live_stock_report_vals.update({'amz_instance_id': instance.id, })
                fba_live_stock_report = live_inventory_request_report_record.create( \
                    fba_live_stock_report_vals)
                fba_live_stock_report.request_report()
                fba_live_stock_report_ids.append(fba_live_stock_report.id)
            return fba_live_stock_report_ids

        fba_live_stock_report = live_inventory_request_report_record.create(
            fba_live_stock_report_vals)
        fba_live_stock_report.request_report()
        fba_live_stock_report_ids.append(fba_live_stock_report.id)
        return fba_live_stock_report_ids

    def prepare_merchant_report_dict(self, seller):
        """
        Added by Udit
        :return: This method will prepare merchant' informational dictionary which will
                 passed to  amazon api calling method.
        """
        account = self.env['iap.account'].search([('service_name', '=', 'amazon_ept')])
        dbuuid = self.env['ir.config_parameter'].sudo().get_param('database.uuid')
        return {
            'merchant_id': seller.merchant_id and str(seller.merchant_id) or False,
            'auth_token': seller.auth_token and str(seller.auth_token) or False,
            'app_name': 'amazon_ept',
            'account_token': account.account_token,
            'emipro_api': 'get_reports_v13',
            'dbuuid': dbuuid,
            'amazon_marketplace_code': seller.country_id.amazon_marketplace_code or
                                       seller.country_id.code,
        }

    def get_reports(self, vals):
        """
        Addded by Udit
        This method will get settlement report data from amazon and create it's record in odoo.
        :return: This method will redirecting us to settlement report tree view.
        """

        tree_id = vals.get('tree_id')
        form_id = vals.get('form_id')
        seller = self.seller_id
        if not seller:
            raise UserError(_('Please select Seller'))

        start_date, end_date = self.get_fba_reports_date_format()
        kwargs = self.sudo().prepare_merchant_report_dict(seller)
        kwargs.update(
            {'report_type': vals.get('report_type'), 'start_date': start_date,
             'end_date': end_date})
        response = iap_tools.iap_jsonrpc(DEFAULT_ENDPOINT + '/iap_request', params=kwargs, timeout=1000)
        if response.get('reason'):
            return UserError(_(response.get('reason')))

        list_of_wrapper = response.get('result')
        odoo_report_ids = self.prepare_fba_report_vals(list_of_wrapper, vals.get('start_date'),
                                                       vals.get('end_date'), vals.get('model_obj'),
                                                       vals.get('sequence'))
        if self._context.get('is_auto_process'):
            return odoo_report_ids

        return {
            'type': 'ir.actions.act_window',
            'name': vals.get('name'),
            'res_model': vals.get('res_model'),
            'domain': [('id', 'in', odoo_report_ids)],
            'views': [(tree_id.id, 'tree'), (form_id.id, 'form')],
            'view_id': tree_id.id,
            'target': 'current'
        }

    def get_fba_reports_date_format(self):
        """
        Added by Udit
        This method will convert selected time duration in specific format to send it to amazon.
        If start date and end date is empty then system will automatically select past 90 days
        time duration.
        :return: This method will return converted start and end date.
        """
        start_date = self.report_start_date
        end_date = self.report_end_date
        if start_date:
            db_import_time = time.strptime(str(start_date), "%Y-%m-%d %H:%M:%S")
            db_import_time = time.strftime("%Y-%m-%dT%H:%M:%S", db_import_time)
            start_date = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(
                time.mktime(time.strptime(db_import_time, "%Y-%m-%dT%H:%M:%S"))))
            start_date = str(start_date) + 'Z'
        else:
            today = datetime.now()
            earlier = today - timedelta(days=90)
            earlier_str = earlier.strftime("%Y-%m-%dT%H:%M:%S")
            start_date = earlier_str + 'Z'
        if end_date:
            db_import_time = time.strptime(str(end_date), "%Y-%m-%d %H:%M:%S")
            db_import_time = time.strftime("%Y-%m-%dT%H:%M:%S", db_import_time)
            end_date = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(
                time.mktime(time.strptime(db_import_time, "%Y-%m-%dT%H:%M:%S"))))
            end_date = str(end_date) + 'Z'
        else:
            today = datetime.now()
            earlier_str = today.strftime("%Y-%m-%dT%H:%M:%S")
            end_date = earlier_str + 'Z'
        return start_date, end_date

    def prepare_fba_report_vals(self, list_of_wrapper, start_date, end_date, model_obj, sequence):
        """
        Added by Udit
        This method will create settlement report and it's attachments from the amazon api response.
        :param list_of_wrapper: Dictionary of amazon api response.
        :param start_date: Selected start date in wizard in specific format.
        :param end_date: Selected end date in wizard in specific format.
        :return: This method will return list of newly created settlement report id.
        """
        odoo_report_ids = []
        if list_of_wrapper is None:
            return []

        for result in list_of_wrapper:
            reports = []
            if not isinstance(result.get('ReportInfo', []), list):
                reports.append(result.get('ReportInfo', []))
            else:
                reports = result.get('ReportInfo', [])
            for report in reports:
                request_id = report.get('ReportRequestId', {}).get('value', '')
                report_id = report.get('ReportId', {}).get('value', '')
                report_type = report.get('ReportType', {}).get('value', '')
                report_exist = model_obj.search(
                    ['|', ('report_request_id', '=', request_id), ('report_id', '=', report_id),
                     ('report_type', '=', report_type)])
                if report_exist:
                    report_exist = report_exist[0]
                    odoo_report_ids.append(report_exist.id)
                    continue
                vals = self.prepare_fba_report_vals_for_create(report_type, request_id, report_id,
                                                               start_date, end_date,
                                                               sequence)
                report_rec = model_obj.create(vals)
                report_rec.get_report()
                self._cr.commit()
                odoo_report_ids.append(report_rec.id)
        return odoo_report_ids

    def prepare_fba_report_vals_for_create(self, report_type, request_id, report_id, start_date,
                                           end_date, sequence):
        """
        Added by Udit
        :param report_type: Report type.
        :param request_id: Amazon request id.
        :param report_id: Amazon report id.
        :param start_date: Selected start date in wizard in specific format.
        :param end_date: Selected end date in wizard in specific format.
        :return: This method will prepare and return settlement report vals.
        """
        try:
            if sequence:
                report_name = sequence.next_by_id()
            else:
                report_name = '/'
        except:
            report_name = '/'
        return {
            'name': report_name,
            'report_type': report_type,
            'report_request_id': request_id,
            'report_id': report_id,
            'start_date': start_date,
            'end_date': end_date,
            'state': '_DONE_',
            'seller_id': self.seller_id.id,
            'user_id': self._uid,
        }

    def create_sync_active_products(self, seller_id, instance_id,
                                    update_price_in_pricelist, auto_create_product):
        """
            Process will create record of Active Product List of selected seller and instance
            @:param - seller_id - selected seller from wizard
            @:param - instance_id - selected instance from wizard
            @:param - update_price_in_pricelist - Boolean for create pricelist or not
            @:param - auto_create_product - Boolean for create product or not
            @author: Deval Jagad (16/11/2019)
        """
        if not instance_id:
            raise UserError(_('Please Select Instance'))
        active_product_listing_obj = self.env['active.product.listing.report.ept']
        form_id = self.env.ref('amazon_ept.active_product_listing_form_view_ept')
        vals = {'instance_id': instance_id.id,
                'seller_id': seller_id.id,
                'update_price_in_pricelist': update_price_in_pricelist or False,
                'auto_create_product': auto_create_product or False
                }

        active_product_listing = active_product_listing_obj.create(vals)
        try:
            active_product_listing.request_report()
        except Exception as exception:
            raise UserError(_(exception))
        return {
            'type': 'ir.actions.act_window',
            'name': 'Active Product List',
            'res_model': 'active.product.listing.report.ept',
            'res_id': active_product_listing.id,
            'views': [(form_id.id, 'form')],
            'view_id': form_id.id,
            'target': 'current'
        }

    def download_sample_attachment(self):
        """
        This Method relocates download sample file of amazon.
        :return: This Method return file download file.
        @author: Deval Jagad (26/12/2019)
        """
        attachment = self.env['ir.attachment'].search([('name', '=', 'import_product_sample.xls')])
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/%s?download=true' % (attachment.id),
            'target': 'new',
            'nodestroy': False,
        }

    def import_csv_file(self):
        """
        This Method relocates Import product csv in amazon listing and mapping of amazon product listing.
        """
        if not self.choose_file:
            raise UserError(_('Please Upload File.'))

        reader = self.read_import_csv_file()

        product_obj = self.env["product.product"]
        amazon_product_ept_obj = self.env['amazon.product.ept']
        comman_log_line_obj = self.env['common.log.lines.ept']
        model_id = comman_log_line_obj.get_model_id('product.product')
        amz_product_model_id = comman_log_line_obj.get_model_id('amazon.product.ept')
        instance_dict = {}
        log_rec = self.create_amz_product_map_log()
        #get import file headers name
        headers = reader.fieldnames
        skip_header = self.read_import_file_header(headers, model_id, log_rec, comman_log_line_obj)
        if not skip_header:
            for line in reader:
                skip_line = self.read_import_csv_file_with_product_list(line, reader, model_id, log_rec, comman_log_line_obj)
                if not skip_line:
                    odoo_default_code = line.get('Internal Reference')
                    seller_sku = line.get('Seller SKU')
                    amazon_marketplace = line.get('Marketplace')
                    fulfillment = line.get('Fulfillment')
                    instance = False

                    if amazon_marketplace:
                        instance = instance_dict.get(amazon_marketplace)
                        if not instance:
                            instance = self.seller_id.instance_ids.filtered(
                                    lambda l: l.marketplace_id.name == amazon_marketplace)
                            instance_dict.update({amazon_marketplace: instance})

                    if instance and fulfillment and seller_sku:
                        if not odoo_default_code:
                            message = """ Internal Reference Not found for seller sku %s """ % (seller_sku)
                            comman_log_line_obj.amazon_create_product_log_line(message, model_id, product_id, seller_sku, fulfillment, log_rec)

                            continue

                        product_id = product_obj.search(['|', ("default_code", "=ilike", odoo_default_code),
                                                         ("barcode", "=ilike", odoo_default_code)], limit=1)
                        amazon_product_id = amazon_product_ept_obj.search_amazon_product(instance.id, seller_sku,
                                                                                         fulfillment_by=fulfillment)
                        if amazon_product_id and amazon_product_id.product_id.id != product_id.id:
                            amazon_product_id.product_id = product_id
                            message = """ Odoo Product [%s] has been updated for Seller Sku [%s]""" \
                                      % (odoo_default_code, seller_sku)
                            comman_log_line_obj.amazon_create_product_log_line(
                                message, model_id, amazon_product_id.product_id, seller_sku, fulfillment, log_rec)
                            continue

                        if amazon_product_id:
                            message = """ Amazon product found for seller sku %s and Internal Reference %s""" \
                                      % (seller_sku, odoo_default_code)
                            comman_log_line_obj.amazon_create_product_log_line(message, model_id, amazon_product_id.product_id, seller_sku, fulfillment, log_rec)
                            continue

                        if not product_id:
                            product_id = self.get_odoo_product_csv_data_ept(line, fulfillment, log_rec)

                        if not product_id:
                            continue

                        self.create_amazon_listing(instance, product_id, line)
                        message = """ Amazon product created for seller sku %s || Instance %s and mapped with odoo product %s """ % (
                            seller_sku, instance.name, product_id.name)
                        comman_log_line_obj.amazon_create_product_log_line(message, amz_product_model_id, product_id, seller_sku, fulfillment, log_rec)
        if not log_rec.log_lines:
            log_rec.unlink()

        return {
            'effect': {
                'fadeout': 'slow',
                'message': "All products import successfully!",
                'img_url': '/web/static/src/img/smile.svg',
                'type': 'rainbow_man',
            }
        }

    def read_import_csv_file(self):
        """
        This Method read selected csv, xls or xlsx file and check valid file format
        if not valid format then raise warning if valid then read file.
        :return: This Method return reader object of selected file.
        @author : Kishan Sorani (09-04-2021)

	    @modified by: Sunil Khatri (24/04/2021)
        """
        if os.path.splitext(self.file_name)[1].lower() not in ['.csv', '.xls', '.xlsx']:
            raise ValidationError(_("Invalid file format. You are only allowed to upload .csv, .xls or .xlsx "
                              "file."))
        try:
            data = StringIO(base64.b64decode(self.choose_file).decode())
        except Exception as ex:
            raise UserError(_(ex))
        # set reader variable when selected file extension is .csv and file format is csv
        if os.path.splitext(self.file_name)[1].lower() == '.csv':
            if self.delimiter == "tab":
                reader = csv.DictReader(data, delimiter='\t')
            elif self.delimiter == "semicolon":
                reader = csv.DictReader(data, delimiter=';')
            else:
                reader = csv.DictReader(data, delimiter=',')
        # set reader variable when selected file extension either .xls or .xlsx and file format is xls
        else:
            reader = csv.DictReader(data)
        return reader

    def create_amz_product_map_log(self):
        log_book_obj = self.env['common.log.book.ept']
        log_vals = {
            'active': True,
            'type': 'import',
            'model_id': self.env['ir.model']._get('amazon.product.ept').id,
            'res_id': self.id,
            'module': 'amazon_ept'
        }
        log_rec = log_book_obj.create(log_vals)
        return log_rec

    def read_import_csv_file_with_product_list(self, line, reader, model_id, log_rec, comman_log_line_obj):
        """
        This method read import csv, xls or xlsx file and check file columns name are valid name
        or columns entries of Title,Seller SKU,Internal Reference,Marketplace or Fulfillment
        are fill or not.If either Column name invalid or missing then create log record also
        create log record if column field are blank.
        @param : line - Iterable line of csv file
        @:param : reader - object of readable file
        @:param : model_id - object of model for created log line
        @:param : log_rec - object of common log book model
        @:param : comman_log_line_obj - object of common log lines book model
        :return: This Method return boolean(True/False).
        @author: Kishan Sorani
        """
        seller_sku = line.get('Seller SKU')
        fullfillment_by = line.get('Fulfillment')

        skip_line = False
        if not line.get('Seller SKU'):
            message = "Line is skipped Seller SKU is required to create an product at line %s" % (reader.line_num)
            comman_log_line_obj.amazon_create_product_log_line(message, model_id, False, seller_sku, fullfillment_by, log_rec)
            skip_line = True
        elif self.auto_create_product and not line.get('Title'):
            message = 'Line is skipped Title is required to create an product at line %s' % (reader.line_num)
            comman_log_line_obj.amazon_create_product_log_line(message, model_id, False, seller_sku, fullfillment_by, log_rec)
            skip_line = True
        elif not line.get('Internal Reference'):
            message = 'Line is skipped Internal Reference is required to create an product at line %s' % (reader.line_num)
            comman_log_line_obj.amazon_create_product_log_line(message, model_id, False, seller_sku, fullfillment_by, log_rec)
            skip_line = True
        elif not line.get('Marketplace'):
            message = 'Line is skipped Marketplace is required to create an product at line %s' % (reader.line_num)
            comman_log_line_obj.amazon_create_product_log_line(message, model_id, False, seller_sku, fullfillment_by, log_rec)
            skip_line = True
        elif not line.get('Fulfillment'):
            message = 'Line is skipped Fulfillment is required to create an product at line %s' % (reader.line_num)
            comman_log_line_obj.amazon_create_product_log_line(message, model_id, False, seller_sku, fullfillment_by, log_rec)
            skip_line = True
        return skip_line

    def read_import_file_header(self, headers, model_id, log_rec, comman_log_line_obj):
        """
        This method read import file headers name are correct or not.
        @param : headers - list of import file headers
        @:param : model_id - object of model for created log line
        @:param : log_rec - object of common log book model
        @:param : comman_log_line_obj - object of common log lines book model
        :return: This Method return boolean(True/False).
        @author: Kishan Sorani
        """
        skip_header = False
        if self.auto_create_product and headers[0] != 'Title':
            message = 'Import file is skipped due to header Title is incorrect or blank'
            comman_log_line_obj.amazon_create_product_log_line(message, model_id, False, False,
                                                               False, log_rec)
            skip_header = True

        elif headers[1] != 'Internal Reference':
            message = 'Import file is skipped due to header Internal Reference is incorrect or blank'
            comman_log_line_obj.amazon_create_product_log_line(message, model_id, False, False,
                                                               False, log_rec)
            skip_header = True

        elif headers[2] != 'Seller SKU':
            message = 'Import file is skipped due to header Seller SKU is incorrect or blank'
            comman_log_line_obj.amazon_create_product_log_line(message, model_id, False, False,
                                                               False, log_rec)
            skip_header = True

        elif headers[3] != 'Marketplace':
            message = 'Import file is skipped due to header Marketplace is incorrect or blank'
            comman_log_line_obj.amazon_create_product_log_line(message, model_id, False, False,
                                                               False, log_rec)
            skip_header = True

        elif headers[4] != 'Fulfillment':
            message = 'Import file is skipped due to header Fulfillment is incorrect or blank'
            comman_log_line_obj.amazon_create_product_log_line(message, model_id, False, False,
                                                               False, log_rec)
            skip_header = True
        return skip_header

    def get_odoo_product_csv_data_ept(self, line_vals, fullfillment_by, log_rec):
        """
        This method will get the product vals and  find or create the odoo product.
        :param line_vals : csv file line data.
        return : odoo product.
        """
        product_obj = self.env['product.product']
        amazon_product_ept_obj = self.env['amazon.product.ept']
        comman_log_line_obj = self.env['common.log.lines.ept']
        model_id = comman_log_line_obj.get_model_id('product.product')
        amazon_product_name = line_vals.get('Title')
        odoo_default_code = line_vals.get('Internal Reference')
        seller_sku = line_vals.get('Seller SKU')

        amazon_product = amazon_product_ept_obj.search(['|', ('active', '=', False), ('active', '=', True),
                                                        ('seller_sku', '=', seller_sku)], limit=1)
        product_id = amazon_product.product_id if amazon_product else False

        if not product_id and self.auto_create_product:
            odoo_product_dict = {
                'name': amazon_product_name,
                'default_code': odoo_default_code,
                'type': 'product'
            }
            product_id = product_obj.create(odoo_product_dict)

            message = """ Odoo Product created for seller sku %s and Internal Reference %s """ % (
                seller_sku, odoo_default_code)
            comman_log_line_obj.amazon_create_product_log_line(
                    message, model_id, product_id, seller_sku, fullfillment_by, log_rec)
        if not product_id:
            message = """ Line Skipped due to product not found seller sku %s || Internal 
                                Reference %s """ % (seller_sku, odoo_default_code)
            comman_log_line_obj.amazon_create_product_log_line(
                    message, model_id, False, seller_sku, fullfillment_by, log_rec)


        return product_id

    def create_amazon_listing(self, instance, product_id, line_vals):
        """
        This Method relocates if product exist in odoo and product doesn't exist in
        amazon create amazon product listing.
        :param instance: This arguments relocates instance of amazon.
        :param product_id: product record
        :param line_vals: amazon listing line vals
        :return: This method return boolean(True/False).
        @author: Deval Jagad (26/12/2019)
        """
        amazon_product_ept_obj = self.env['amazon.product.ept']
        amazon_product_name = line_vals.get('Title')
        seller_sku = line_vals.get('Seller SKU')
        fulfillment = line_vals.get('Fulfillment')

        amazon_product_ept_obj.create(
                {'name': amazon_product_name or product_id.name,
                 'fulfillment_by': fulfillment,
                 'product_id': product_id.id,
                 'seller_sku': seller_sku,
                 'instance_id': instance.id,
                 'exported_to_amazon': True})
        return True

    def wizard_create_inbound_shipment_plan(self, instance):
        """
        This method will create shipment plan record of selected seller and instance
        :return:
        @author: Deval Jagad (26/12/2019)
        """
        if not instance:
            raise UserError(_('Please Select Instance'))
        inbound_shipment_plan_obj = self.env['inbound.shipment.plan.ept']
        form_id = self.env.ref('amazon_ept.inbound_shipment_plan_form_view')

        warehouse_id = instance.warehouse_id
        vals = {'instance_id': instance.id,
                'warehouse_id': warehouse_id.id,
                'ship_from_address_id': warehouse_id.partner_id and \
                                        warehouse_id.partner_id.id,
                'company_id': instance.company_id and instance.company_id.id,
                'ship_to_country': instance.country_id and instance.country_id.id
                }
        shipment_plan_id = inbound_shipment_plan_obj.create(vals)

        return {
            'type': 'ir.actions.act_window',
            'name': 'Inbound Shipment Plan',
            'res_model': 'inbound.shipment.plan.ept',
            'res_id': shipment_plan_id.id,
            'views': [(form_id.id, 'form')],
            'view_id': form_id.id,
            'target': 'current'
        }