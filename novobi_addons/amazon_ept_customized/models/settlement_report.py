import base64
import csv
import logging
from datetime import datetime
from io import StringIO
from odoo import models, fields, api, _

_logger = logging.getLogger(__name__)


class SettlementReportEpt(models.Model):

    _inherit = "settlement.report.ept"

    @staticmethod
    def format_amz_settlement_report_date(date):
        """
        SRN-68
        Override: posted_date -> posted_date[:10]
        """
        return datetime.strptime(date[:10], '%Y-%m-%d')

    def process_settlement_report_file(self):
        """
        SRN-68
        Override: posted_date -> posted_date[:10]
        """
        self.ensure_one()
        ir_cron_obj = self.env['ir.cron']
        if not self._context.get('is_auto_process', False):
            ir_cron_obj.with_context({'raise_warning': True}).find_running_schedulers( \
                    'ir_cron_auto_process_settlement_report_seller_', self.seller_id.id)
        self.check_instance_configuration_and_attachment_file()
        imp_file = StringIO(base64.b64decode(self.attachment_id.datas).decode())
        content = imp_file.read()
        settlement_reader = csv.DictReader(content.splitlines(), delimiter='\t')
        journal = self.instance_id.settlement_report_journal_id
        seller = self.seller_id
        bank_statement = False
        settlement_id = ''
        order_list_item_price = {}
        order_list_item_fees = {}

        refund_list_item_price = {}
        create_or_update_refund_dict = {}
        amazon_product_obj = self.env['amazon.product.ept']
        partner_obj = self.env['res.partner']
        amazon_other_transaction_list = {}
        product_dict = {}
        order_dict = {}

        for row in settlement_reader:
            settlement_id = row.get('settlement-id')
            if not bank_statement:
                bank_statement = self.create_settlement_report_bank_statement(row, journal,
                                                                              settlement_id)
                if not bank_statement:
                    break
            if not row.get('transaction-type'):
                continue
            order_ref = row.get('order-id')
            shipment_id = row.get('shipment-id')
            order_item_code = row.get('order-item-code').lstrip('0')
            posted_date = row.get('posted-date')
            fulfillment_by = row.get('fulfillment-id')
            adjustment_id = row.get('adjustment-id')
            # changed part: posted_date -> posted_date[:10]
            posted_date = datetime.strptime(posted_date[:10], '%Y-%m-%d')
            # end of changed part
            amount = float(row.get('amount').replace(',', '.'))
            if row.get('transaction-type') in ['Order', 'Refund']:
                if row.get('amount-description').__contains__('MarketplaceFacilitator') or row.get(
                        'amount-type') == 'ItemFees':
                    order_list_item_fees = self.prepare_order_list_item_fees_ept( \
                            row, settlement_id, amount, posted_date, order_list_item_fees)
                    continue
                order_ids = order_dict.get((order_ref, shipment_id, order_item_code))
                if not order_ids:
                    amz_order = self.get_settlement_report_amazon_order_ept(row)
                    order_ids = tuple(amz_order.ids)
                    order_dict.update({(order_ref, shipment_id, order_item_code): order_ids})

                partner = partner_obj.with_context(is_amazon_partner=True)._find_accounting_partner(
                        amz_order.mapped('partner_id'))

                if row.get('transaction-type') == 'Order':
                    key = (order_ref, order_ids, posted_date, fulfillment_by, partner.id, shipment_id)
                    if not order_list_item_price.get(key):
                        order_list_item_price.update({key: amount})
                    else:
                        existing_amount = order_list_item_price.get(key, 0.0)
                        order_list_item_price.update({key: existing_amount + amount})

                elif row.get('transaction-type') == 'Refund':
                    product_id = product_dict.get(row.get('sku'))
                    if not product_id:
                        amazon_product = amazon_product_obj.search( \
                                [('seller_sku', '=', row.get('sku')),
                                 ('instance_id', '=', self.instance_id.id)], limit=1)
                        product_id = amazon_product.product_id.id
                        product_dict.update({row.get('sku'): amazon_product.product_id.id})
                    key = (order_ref, order_ids, posted_date, fulfillment_by, partner.id, adjustment_id)
                    if not refund_list_item_price.get(key):
                        refund_list_item_price.update({key: amount})
                    else:
                        existing_amount = refund_list_item_price.get(key, 0.0)
                        refund_list_item_price.update({key: existing_amount + amount})

                    create_or_update_refund_dict = self.get_settlement_refund_dict_ept(row, key,
                                                                                       product_id,
                                                                                       create_or_update_refund_dict)
            else:
                if row.get('amount-type') in ['other-transaction', 'FBA Inventory Reimbursement']:
                    key = (row.get('amount-type'), posted_date, row.get('amount-description'), settlement_id)
                    existing_amount = amazon_other_transaction_list.get(key, 0.0)
                    amazon_other_transaction_list.update({key: existing_amount + amount})
                else:
                    key = (row.get('amount-type'), posted_date, '', settlement_id)
                    existing_amount = amazon_other_transaction_list.get(key, 0.0)
                    amazon_other_transaction_list.update({key: existing_amount + amount})

        if not bank_statement:
            return True
        self.make_amazon_fee_entry(bank_statement, order_list_item_fees)
        if amazon_other_transaction_list:
            self.make_amazon_other_transactions(seller, bank_statement, amazon_other_transaction_list)

        if order_list_item_price:
            self.process_settlement_orders(bank_statement, settlement_id, order_list_item_price) or {}

        if refund_list_item_price:
            self.process_settlement_refunds(bank_statement.id, settlement_id, \
                                            refund_list_item_price)

        # Create manually refund in ERP whose returned not found in the system
        if create_or_update_refund_dict:
            self.create_refund_invoices(create_or_update_refund_dict, bank_statement)

        self.write({'statement_id': bank_statement.id, 'state': 'imported'})
        return True

    def prepare_attachments(self, data, marketplace, start_date, end_date, currency_rec):
        """
        SRN-69
        Inherit: set Seller and Instance to settlement report
        """
        super(SettlementReportEpt, self).prepare_attachments(data, marketplace, start_date, end_date, currency_rec)

        if not self.instance_id:
            marketplace_id = self.env['amazon.marketplace.ept'].search([('name', '=', marketplace)])
            if marketplace_id:
                instance_id = self.env['amazon.instance.ept'].sudo().search([('marketplace_id', 'in', marketplace_id.ids)])
                if instance_id:
                    self.write({
                        'instance_id': instance_id[0].id,
                        'seller_id': instance_id[0].seller_id.id
                    })

