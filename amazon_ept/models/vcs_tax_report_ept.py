# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.

"""
Added class and methods to request for VCS tax report, import and process that report.
"""

import time
import base64
from io import StringIO
import csv
import logging
from datetime import datetime, timedelta
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo.addons.iap.tools import iap_tools
from ..endpoint import DEFAULT_ENDPOINT

_logger = logging.getLogger("Amazon")


class VcsTaxReport(models.Model):
    """
    Added class to import amazon VCS tax report.
    """
    _name = 'amazon.vcs.tax.report.ept'
    _description = 'Amazon VCS Tax Report'
    _inherit = ['mail.thread']
    _order = 'id desc'

    def _compute_log_count(self):
        """
        Sets count of log lines for the VCS report.
        @change: By Maulik Barad on Date 20-Jan-2019.
        """
        log_obj = self.env['common.log.book.ept']
        model_id = self.env['ir.model']._get('amazon.vcs.tax.report.ept').id
        self.log_count = log_obj.search_count([('res_id', '=', self.id), ('model_id', '=', model_id)])

    def _compute_no_of_invoices(self):
        """
        This method is used to count the number of invoices created via VCS tax report.
        """
        for record in self:
            record.invoice_count = len(record.invoice_ids)

    name = fields.Char(size=256)
    start_date = fields.Datetime(help="Report Start Date")
    end_date = fields.Datetime(help="Report End Date")
    report_request_id = fields.Char(size=256, string='Report Request ID',
                                    help="Report request id to recognise unique request")
    report_id = fields.Char(size=256, string='Report ID',
                            help="Unique Report id for recognise report in Odoo")
    report_type = fields.Char(size=256, help="Amazon Report Type")
    seller_id = fields.Many2one('amazon.seller.ept', string='Seller', copy=False)
    state = fields.Selection(
            [('draft', 'Draft'), ('_SUBMITTED_', 'SUBMITTED'), ('_IN_PROGRESS_', 'IN_PROGRESS'),
             ('_CANCELLED_', 'CANCELLED'), ('_DONE_', 'DONE'),
             ('partially_processed', 'Partially Processed'),
             ('_DONE_NO_DATA_', 'DONE_NO_DATA'), ('processed', 'PROCESSED')
             ],
            string='Report Status', default='draft')
    attachment_id = fields.Many2one('ir.attachment', string="Attachment")
    auto_generated = fields.Boolean('Auto Generated Record ?', default=False)
    log_count = fields.Integer(compute="_compute_log_count")
    invoice_count = fields.Integer(compute="_compute_no_of_invoices",
                                   string="Invoices Count")
    invoice_ids = fields.Many2many('account.move', 'vcs_processed_invoices', string="Invoices")

    def unlink(self):
        """
        This method is inherited to do not allow to delete te processed report.
        """
        for report in self:
            if report.state == 'processed':
                raise UserError(_('You cannot delete processed report.'))
        return super(VcsTaxReport, self).unlink()

    @api.model
    def default_get(self, fields):
        """
        inherited to update the report type.
        """
        res = super(VcsTaxReport, self).default_get(fields)
        if not fields:
            return res
        res.update({'report_type': '_SC_VAT_TAX_REPORT_', })
        return res

    @api.model
    def create(self, vals):
        """
        inherited to update the name of VCS tax report.
        """
        try:
            sequence = self.env.ref('amazon_ept.seq_import_vcs_report_job')
            if sequence:
                report_name = sequence.next_by_id()
            else:
                report_name = '/'
        except:
            report_name = '/'
        vals.update({'name': report_name})
        return super(VcsTaxReport, self).create(vals)

    @api.onchange('seller_id')
    def on_change_seller_id(self):
        """
        Based on seller it will update the start and end date.
        """
        value = {}
        if self.seller_id:
            start_date = datetime.now() + timedelta(
                    days=self.seller_id.fba_vcs_report_days * -1 or -3)
            value.update({'start_date': start_date, 'end_date': datetime.now()})
        return {'value': value}

    def download_report(self):
        """
        This method is used to download VCS tax report.
        """
        self.ensure_one()
        if self.attachment_id:
            return {
                'type': 'ir.actions.act_url',
                'url': '/web/content/%s?download=true' % self.attachment_id.id,
                'target': 'download',
            }
        return True

    def list_of_logs(self):
        """
        This method is used to display the number of logs from the VCS tax report.
        """
        log_line_obj = self.env['common.log.lines.ept']
        model_id = log_line_obj.get_model_id('amazon.vcs.tax.report.ept')
        action = {
            'domain': "[('res_id', '=', " + str(self.id) + " ), ('model_id','='," + str(model_id) + ")]",
            'name': 'VCS Report Logs',
            'view_mode': 'tree,form',
            'res_model': 'common.log.book.ept',
            'type': 'ir.actions.act_window',
        }
        return action

    def report_start_and_end_date(self):
        """
        This method will return the report start and end date.
        """
        start_date, end_date = self.start_date, self.end_date
        if start_date:
            db_import_time = time.strptime(str(start_date), "%Y-%m-%d %H:%M:%S")
            db_import_time = time.strftime("%Y-%m-%dT%H:%M:%S", db_import_time)
            start_date = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(
                    time.mktime(time.strptime(db_import_time, "%Y-%m-%dT%H:%M:%S"))))
            start_date = str(start_date) + 'Z'
        else:
            today = datetime.now()
            earlier = today - timedelta(days=30)
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

    def request_report(self):
        """
        This method will request for the VCS tax report and update report history in odoo.
        """
        common_log_book_obj = self.env["common.log.book.ept"]
        seller, report_type, start_date, end_date = self.seller_id, self.report_type, \
                                                    self.start_date, self.end_date
        if not seller:
            raise UserError(_('Please select Seller'))

        start_date, end_date = self.report_start_and_end_date()

        kwargs = self.prepare_amazon_request_report_kwargs(seller)
        kwargs.update({
            'emipro_api': 'request_report_v13',
            'report_type': report_type,
            'start_date': start_date,
            'end_date': end_date,
        })
        response = iap_tools.iap_jsonrpc(DEFAULT_ENDPOINT + '/iap_request', params=kwargs, timeout=1000)
        if response.get('reason'):
            if self._context.get('is_auto_process'):
                common_log_book_obj.create({
                    'type': 'import',
                    'module': 'amazon_ept',
                    'active': True,
                    'log_lines': [(0, 0, {'message': response.get('reason')})]
                })
            else:
                raise UserError(_(response.get('reason')))
        else:
            result = response.get('result')
            self.update_report_history(result)
        return True

    def update_report_history(self, request_result):
        """
        Update Report History in odoo
        :param request_result:
        :return:
        """
        report_info = request_result.get('ReportInfo', {})
        report_request_info = request_result.get('ReportRequestInfo', {})
        request_id = report_state = report_id = False
        if report_request_info:
            request_id = str(report_request_info.get('ReportRequestId', {}).get('value', ''))
            report_state = report_request_info.get('ReportProcessingStatus', {}).get('value',
                                                                                     '_SUBMITTED_')
            report_id = report_request_info.get('GeneratedReportId', {}).get('value', False)
        elif report_info:
            report_id = report_info.get('ReportId', {}).get('value', False)
            request_id = report_info.get('ReportRequestId', {}).get('value', False)

        if report_state == '_DONE_' and not report_id:
            self.get_report_list()
        vals = {}
        if not self.report_request_id and request_id:
            vals.update({'report_request_id': request_id})
        if report_state:
            vals.update({'state': report_state})
        if report_id:
            vals.update({'report_id': report_id})
        self.write(vals)
        return True

    def get_report_list(self):
        """
        This method is used to get report data based on VCS report request id and process
        response and update report request history in odoo.
        """
        self.ensure_one()
        common_log_book_obj = self.env['common.log.book.ept']
        list_of_wrapper = []
        if not self.seller_id:
            raise UserError(_('Please select seller'))
        if not self.request_id:
            return True

        kwargs = self.prepare_amazon_request_report_kwargs(self.seller_id)
        kwargs.update({'emipro_api': 'get_report_list_v13',
                       'request_id': [self.request_id]})

        response = iap_tools.iap_jsonrpc(DEFAULT_ENDPOINT + '/iap_request', params=kwargs, timeout=1000)
        if response.get('reason'):
            if self._context.get('is_auto_process'):
                common_log_book_obj.create({
                    'type': 'import',
                    'module': 'amazon_ept',
                    'active': True,
                    'log_lines': [(0, 0, {'message': 'VCS Report Process ' + response.get('reason')})]})
            else:
                raise UserError(_(response.get('reason')))
        else:
            list_of_wrapper = response.get('result')

        for result in list_of_wrapper:
            self.update_report_history(result)
        return True

    def get_report_request_list(self):
        """
        This method will request for get report request list based on report_request_id
        and process response and update report history in odoo.
        """
        self.ensure_one()
        if not self.seller_id:
            raise UserError(_('Please select Seller'))
        if not self.report_request_id:
            return True

        kwargs = self.prepare_amazon_request_report_kwargs(self.seller_id)
        kwargs.update({'emipro_api': 'get_report_request_list_v13',
                       'request_ids': (self.report_request_id)})

        response = iap_tools.iap_jsonrpc(DEFAULT_ENDPOINT + '/iap_request', params=kwargs, timeout=1000)
        if not response.get('reason'):
            list_of_wrapper = response.get('result')
        else:
            raise UserError(_(response.get('reason')))
        for result in list_of_wrapper:
            self.update_report_history(result)
        return True

    def get_report(self):
        """
        This method is used to get vcs tax report and create attachments and post the message.
        """
        self.ensure_one()
        common_log_book_obj = self.env['common.log.book.ept']
        result = {}
        seller = self.seller_id
        if not seller:
            raise UserError(_('Please select seller'))
        if not self.report_id:
            return True

        kwargs = self.prepare_amazon_request_report_kwargs(self.seller_id)
        kwargs.update({'emipro_api': 'get_report_v13',
                       'report_id': self.report_id,
                       'amz_report_type': 'vcs_tax_report'})
        response = iap_tools.iap_jsonrpc(DEFAULT_ENDPOINT + '/iap_request', params=kwargs, timeout=1000)
        if response.get('reason'):
            if self._context.get('is_auto_process'):
                common_log_book_obj.create({
                    'type': 'import',
                    'module': 'amazon_ept',
                    'active': True,
                    'log_lines': [
                        (0, 0, {'message': 'VCS Report Process ' + response.get('reason')})]
                })
            else:
                raise UserError(_(response.get('reason')))
        else:
            result = response.get('result')
        if result:
            file_name = "VCS_Tax_report_" + time.strftime("%Y_%m_%d_%H%M%S") + '.csv'
            attachment = self.env['ir.attachment'].create({
                'name': file_name,
                'datas': result.encode(),
                'res_model': 'mail.compose.message',
                'type': 'binary'
            })
            self.message_post(body=_("<b>VCS Tax Report Downloaded</b>"),
                              attachment_ids=attachment.ids)
            self.write({'attachment_id': attachment.id})
        return True

    def prepare_amazon_request_report_kwargs(self, seller):
        """
        Define common method to request for VCX tax report operations.
        """
        account = self.env['iap.account'].search([('service_name', '=', 'amazon_ept')])
        dbuuid = self.env['ir.config_parameter'].sudo().get_param('database.uuid')
        instances_obj = self.env['amazon.instance.ept']
        instances = instances_obj.search([('seller_id', '=', seller.id)])
        marketplaceids = tuple(map(lambda x: x.market_place_id, instances))

        return {'merchant_id': seller.merchant_id and str(seller.merchant_id) or False,
                'auth_token': seller.auth_token and str(seller.auth_token) or False,
                'app_name': 'amazon_ept',
                'account_token': account.account_token,
                'dbuuid': dbuuid,
                'amazon_marketplace_code': seller.country_id.amazon_marketplace_code or
                                           seller.country_id.code,
                'marketplaceids': marketplaceids,
                }

    def auto_import_vcs_tax_report(self, args={}):
        """
        Define method to auto process for import vcs tax report.
        """
        seller_id = args.get('seller_id', False)
        if seller_id:
            seller = self.env['amazon.seller.ept'].search([('id', '=', seller_id)])
            start_date = datetime.now() + timedelta(days=seller.fba_vcs_report_days * -1 or -3)
            start_date = start_date.strftime("%Y-%m-%d %H:%M:%S")
            date_end = datetime.now()
            date_end = date_end.strftime("%Y-%m-%d %H:%M:%S")
            vcs_report = self.create({'report_type': '_SC_VAT_TAX_REPORT_',
                                      'seller_id': seller_id,
                                      'start_date': start_date,
                                      'end_date': date_end,
                                      'state': 'draft',
                                      'auto_generated': True,
                                      })
            vcs_report.request_report()
            seller.write({'vcs_report_last_sync_on': date_end})
        return True

    def amz_search_or_create_logs_ept(self):
        common_log_book_obj = self.env['common.log.book.ept']
        model_id = self.env['ir.model']._get('amazon.vcs.tax.report.ept').id
        log_rec = common_log_book_obj.search([('module', '=', 'amazon_ept'), ('model_id', '=', model_id), \
                                              ('res_id', '=', self.id)])

        if log_rec and log_rec.log_lines:
            log_rec.log_lines.unlink()

        if not log_rec:
            log_rec = common_log_book_obj.amazon_create_transaction_log('import', model_id, self.id)
        return log_rec

    def process_vcs_tax_report_file(self):
        """
        @change: By Maulik Barad on Date 20-Jan-2019.

        Updated  by Twinkalc on 13-Mar-2021
        Updated code to set an invoice url and VCS invoice number into the invoice and refund
        """
        self.ensure_one()
        country_dict = {}
        instance_dict = {}
        ship_from_country_dict = {}
        warehouse_country_dict = {}
        amazon_prod_dict = {}
        vcs_invoice_ids = []
        line_no = 1
        commit_flag = 1

        log = self.amz_search_or_create_logs_ept()
        transaction_line_ids = []
        amazon_seller = self.seller_id or False
        if not self.attachment_id:
            raise UserError(_("There is no any report are attached with this record."))

        imp_file = self.decode_amazon_encrypted_vcs_attachments_data(self.attachment_id, log)
        reader = csv.DictReader(imp_file, delimiter=',')
        for row in reader:
            line_no += 1
            order_id = row.get('Order ID', '')
            marketplace_id = row.get('Marketplace ID', '')
            sku = row.get('SKU', '')

            message = self.check_vcs_report_file_data_ept(row, line_no)
            if message:
                transaction_line_ids.append((0, 0, {'message': message, 'order_ref': order_id,
                                                    'default_code': sku}))
                continue

            country = self.find_vcs_country_ept(country_dict, marketplace_id)
            if not country:
                message = 'Country with code %s not found in line %d' % (marketplace_id, line_no)
                transaction_line_ids.append((0, 0, {'message': message, 'order_ref': order_id}))
                continue

            instance = self.find_vcs_instance_ept(country, amazon_seller, instance_dict)
            if not instance:
                message = 'Instance with %s Country and %s Seller not found in line %d' \
                          % (country.name, amazon_seller.name, line_no)
                transaction_line_ids.append((0, 0, {'message': message, 'order_ref': order_id}))
                continue

            sale_order = self.find_amazon_vcs_sale_order_ept(row, instance, \
                                                             ship_from_country_dict,
                                                             warehouse_country_dict)
            if not sale_order:
                message = 'Sale Order - %s not found in line %d' % (order_id, line_no)
                transaction_line_ids.append((0, 0, {'message': message, 'order_ref': order_id}))
                continue

            if sale_order.state == 'draft':
                message = "Sale Order isn't Confirmed, Draft Quotation - %s found in line %d" \
                          % (order_id, line_no)
                transaction_line_ids.append((0, 0, {'message': message, 'order_ref': order_id}))
                continue

            fulfillment_by = sale_order.amz_fulfillment_by
            amz_prod = self.find_amazon_vcs_product_ept(amazon_prod_dict, sku, instance, fulfillment_by)
            if not amz_prod:
                message = 'Amazon Product not found with %s Seller SKU in line %d' % (sku, line_no)
                transaction_line_ids.append((0, 0, {'message': message, 'order_ref': order_id,
                                                    'default_code': sku}))
                continue

            odoo_product_id = amz_prod.product_id.id if amz_prod.product_id else False
            if not odoo_product_id:
                continue

            vcs_invoice_ids, transaction_line_ids = self.process_vcs_report_data_ept(row, sale_order, odoo_product_id,
                                                                                     vcs_invoice_ids,
                                                                                     transaction_line_ids)
            if commit_flag == 10:
                self.env.cr.commit()
                commit_flag = 0
            commit_flag += 1

        self.write({'invoice_ids': [(4, vcs_invoice.id) for vcs_invoice in vcs_invoice_ids]})
        log.write({'log_lines': transaction_line_ids})
        if not log.log_lines:
            self.write({'state': 'processed'})
            log.unlink()
        self.write({'state': 'partially_processed'})
        return True

    def process_vcs_report_data_ept(self, row, sale_order, product_id, vcs_invoice_ids, transaction_line_ids):
        """
        Added by Twinkalc on 13-Mar-2021
        This method will find the invoices or refunds and update the invoice details.
        """
        vcs_invoice_number = row.get('VAT Invoice Number', '')
        transaction_type = row.get('Transaction Type', '')
        invoice_type = 'out_invoice' if transaction_type == 'SHIPMENT' else 'out_refund'
        mismatch_str = 'Invoice' if invoice_type == 'out_invoice' else 'Refund invoice'
        _logger.info("Processing Sale Order %s" %(sale_order.name))
        invoices = sale_order.invoice_ids.filtered(
                lambda x: x.move_type == invoice_type and x.state != 'cancel')
        if not invoices:
            message = '%s not found for order %s' % (mismatch_str, sale_order.name)
            transaction_line_ids.append((0, 0, {'message': message, 'order_ref': sale_order.name}))
            return vcs_invoice_ids, transaction_line_ids

        invoices = invoices.filtered(lambda x : x.vcs_invoice_number != vcs_invoice_number)
        if len(invoices) > 1:
            invoices = invoices.invoice_line_ids.filtered( \
                    lambda l: l.product_id.id == product_id).mapped('move_id')
            if len(invoices) > 1:
                invoices = invoices[0]

        if invoices and not invoices.vcs_invoice_number:
            invoices.write({'invoice_url': row.get('Invoice Url', ''),
                            'vcs_invoice_number': vcs_invoice_number})
            vcs_invoice_ids.append(invoices)
        return vcs_invoice_ids, transaction_line_ids

    def find_vcs_instance_ept(self, country, amazon_seller, instance_dict):
        """
        Added by Twinkalc on 30-sep-2020
        :param country: country record
        :param amazon_seller : amazon seller record
        :param instance_dict : instance dict
        This method will find the instance based on passed country.
        """
        instance_obj = self.env['amazon.instance.ept']
        instance = instance_obj.browse(instance_dict.get((country.id, amazon_seller.id), False))
        if not instance:
            instance = amazon_seller.instance_ids.filtered(lambda x: x.country_id.id == country.id)
            if instance:
                instance_dict.update({(country.id, amazon_seller.id): instance.id})
        return instance

    def check_vcs_report_file_data_ept(self, row, line_no):
        """
        Added by Twinkalc on 30-sep-2020
        :param row: VCS file data
        :param log_line_vals : log lines dict
        :param line_no : processing line no of file
        :return: This method will check the required data exist to process for
        update taxes in order and invoice lines.
        """
        marketplace_id = row.get('Marketplace ID', '')
        invoice_type = row.get('Transaction Type', '')
        order_id = row.get('Order ID', '')
        sku = row.get('SKU', '')
        qty = int(row.get('Quantity', 0)) if row.get('Quantity', 0) else 0.0
        ship_from_country = row.get('Ship From Country', False)
        message = ''

        if not order_id:
            message = 'Order Id not found in line %d' % line_no
            return message

        if not marketplace_id:
            message = 'Marketplace Id not found for order reference %s in line %d' % (order_id, line_no)
            return message

        if not invoice_type:
            message = 'Invoice Type not found in line %d' % line_no
            return message

        if not sku:
            message = 'SKU not found for order reference %s in line %d' % (order_id, line_no)
            return message

        if invoice_type != 'SHIPMENT' and not qty:
            message = 'Qty to refund not found for order reference %s in line %d' % (order_id, line_no)
            return message

        if not ship_from_country:
            message = 'Ship from country not found for order reference %s in line %d' % (order_id, line_no)
            return message

        return message

    def find_vcs_country_ept(self, country_dict, marketplace_id):
        """
        Added by Twinkalc on 30-sep-2020
        :param country_dict : country dict
        :param marketplace_id: marketplace id
        :param  log_line_vals : log line data
        :param line_no : processing line no of file
        :return: This method wil find the country based on amazon_marketplace_code
         and also update the country dict.
        """

        res_country_obj = self.env['res.country']
        country = res_country_obj.browse(country_dict.get(marketplace_id, False))
        if not country:
            country = res_country_obj.search([('amazon_marketplace_code', '=', marketplace_id)], limit=1)
            if not country:
                country = res_country_obj.search([('code', '=', marketplace_id)], limit=1)
            if country:
                country_dict.update({marketplace_id: country.id})
        return country

    def find_amazon_vcs_product_ept(self, amazon_prod_dict, sku, instance, fulfillment_by):
        """
        Added by Twinkalc on 30-sep-2020
        :param amazon_prod_dict : product data dict.
        :param sku: sku
        :param  instance : instance recorc
        :param fulfillment_by : fulfillment_by
        This method will fine tha amazon product based on instance, sku
        and fulfillment_by and update the amazon product dict
        """

        amz_prod_obj = self.env['amazon.product.ept']
        amz_prod = amz_prod_obj.browse( \
                amazon_prod_dict.get((sku, instance.id, fulfillment_by), False))
        if not amz_prod:
            amz_prod = amz_prod_obj.search([('seller_sku', '=', sku), ('instance_id', '=', instance.id),
                                            ('fulfillment_by', '=', fulfillment_by)], limit=1)
            if amz_prod:
                amazon_prod_dict.update( \
                        {(sku, instance.id, fulfillment_by): amz_prod.id})
        return amz_prod

    def find_amazon_vcs_sale_order_ept(self, row, instance, ship_from_country_dict,
                                       warehouse_country_dict):
        """
        Added by Twinkalc on 30-sep-2020
        :param row : file line data
        :param ship_from_country_dict: ship from country dict
        :param  warehouse_country_dict : warehouse data dict based
        on ship from country
        This method will find the sale order.
        return : sale order record.
        """

        res_country_obj = self.env['res.country']
        order_id = row.get('Order ID', False)
        sale_order_obj = self.env['sale.order']
        stock_warehouse_obj = self.env['stock.warehouse']

        ship_from_country = row.get('Ship From Country', False)

        sale_order = sale_order_obj.search(
                [('amz_instance_id', '=', instance.id),
                 ('amz_order_reference', '=', order_id)])
        if len(sale_order) > 1:
            country = res_country_obj.browse(
                    ship_from_country_dict.get(ship_from_country, False))
            if not country:
                country = res_country_obj.search([('code', '=', ship_from_country)], limit=1)
                if country:
                    ship_from_country_dict.update({ship_from_country: country.id})

            warehouses = stock_warehouse_obj.browse(warehouse_country_dict.get(country.id, False))
            if not warehouses:
                warehouses = stock_warehouse_obj.search([('partner_id.country_id', '=', country.id)])
                if warehouses:
                    warehouse_country_dict.update({country.id: warehouses.ids})

            sale_order = sale_order_obj.search([('amz_instance_id', '=', instance.id),
                                                ('amz_order_reference', '=', order_id),
                                                ('warehouse_id', 'in', warehouses.ids)],
                                               limit=1)

        return sale_order

    def auto_process_vcs_tax_report(self, args={}):
        """
        This method is used to auto process the vcs tax report.
        """
        seller_id = args.get('seller_id', False)
        if seller_id:
            seller = self.env['amazon.seller.ept'].search([('id', '=', seller_id)])
            vcs_reports = self.search(
                    [('seller_id', '=', seller.id), ('state', 'in', ['_SUBMITTED_', '_IN_PROGRESS_'])])
            if vcs_reports:
                total_length = len(vcs_reports.ids)
                for x in range(0, total_length, 20):
                    reports = vcs_reports[x:x + 20]
                    for report in reports:
                        report.get_report_request_list()
                        if report.filtered(lambda r: r.state == '_DONE_' and r.report_id):
                            try:
                                report.get_report()

                            except Exception as e:
                                raise UserError(e)
                            time.sleep(2)
                        report.process_vcs_tax_report_file()
                        self._cr.commit()
                        time.sleep(3)

            else:
                reports = self.search([('seller_id', '=', seller.id), ('state', '=', '_DONE_')], order='id asc')
                for report in reports:
                    if not report.attachment_id:
                        while True:
                            try:
                                report.get_report()
                                break
                            except Exception as e:
                                raise UserError(e)
                    try:
                        report.process_vcs_tax_report_file()
                        self._cr.commit()
                    except:
                        continue
                    time.sleep(3)
        return True

    def get_amz_vcs_invoices(self):
        """
        Opens the tree view of Invoices.
        @author: Maulik Barad on Date 20-Jan-2019.
        """
        return {
            'domain': "[('id', 'in', " + str(self.invoice_ids.ids) + " )]",
            'name': 'Invoices',
            'view_mode': 'tree,form',
            'res_model': 'account.move',
            'type': 'ir.actions.act_window',
        }

    def decode_amazon_encrypted_vcs_attachments_data(self, attachment_id, job):
        """
        Added method to decode the encrypted VCS attachments data.
        """
        dbuuid = self.env['ir.config_parameter'].sudo().get_param('database.uuid')
        req = {'dbuuid': dbuuid, 'report_id': self.report_id, 'datas': attachment_id.datas.decode(),
               'amz_report_type': 'vcs_tax_report'}
        response = iap_tools.iap_jsonrpc(DEFAULT_ENDPOINT + '/decode_data', params=req, timeout=1000)
        if response.get('result'):
            try:
                imp_file = StringIO(base64.b64decode(response.get('result')).decode())
            except:
                imp_file = StringIO(base64.b64decode(response.get('result')).decode('ISO-8859-1'))
        elif self._context.get('is_auto_process', False):
            job.log_lines.create({'message': 'Error found in Decryption of Data %s' % response.get('error', '')})
            return False
        else:
            raise UserError(_(response.get('error')))
        return imp_file
