import csv
import base64
from io import StringIO
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class ActiveProductListingReportEpt(models.Model):

    _inherit = "active.product.listing.report.ept"

    def read_import_file_header(self, headers, model_id, log_rec, comman_log_line_obj):
        """
        SRN-53
        Override: change 'fulfilment-channel' to 'fulfillment-channel'
        """
        skip_header = False
        if self.auto_create_product and 'item-name' not in headers:
            message = 'Import file is skipped due to header item-name is incorrect or blank'
            comman_log_line_obj.amazon_create_product_log_line(message, model_id, False, False,
                                                               False, log_rec)
            skip_header = True

        elif 'seller-sku' not in headers:
            message = 'Import file is skipped due to header seller-sku is incorrect or blank'
            comman_log_line_obj.amazon_create_product_log_line(message, model_id, False, False,
                                                               False, log_rec)
            skip_header = True

        elif 'fulfillment-channel' not in headers:
            message = 'Import file is skipped due to header fulfilment-channel is incorrect or blank'
            comman_log_line_obj.amazon_create_product_log_line(message, model_id, False, False,
                                                               False, log_rec)
            skip_header = True
        return skip_header

    def sync_products(self):
        """
        SRN-56
        Override: add company_id condition in search
        """
        self.ensure_one()
        if not self.attachment_id:
            raise UserError(_("There is no any report are attached with this record."))
        if not self.instance_id:
            raise UserError(_("Instance not found "))
        if not self.instance_id.pricelist_id:
            raise UserError(_("Please configure Pricelist in Amazon Marketplace"))

        amazon_product_ept_obj = self.env['amazon.product.ept']
        product_obj = self.env['product.product']
        log_book_obj = self.env['common.log.book.ept']
        comman_log_line_obj = self.env['common.log.lines.ept']

        log_model_id = comman_log_line_obj.get_model_id('active.product.listing.report.ept')
        model_id = comman_log_line_obj.get_model_id('product.product')
        log_rec = log_book_obj.amazon_create_transaction_log('import', log_model_id, \
                                                             self.id)

        imp_file = StringIO(base64.b64decode(self.attachment_id.datas).decode())
        reader = csv.DictReader(imp_file, delimiter='\t')

        price_list_id = self.instance_id.pricelist_id

        # get import file headers name
        headers = reader.fieldnames
        skip_header = self.read_import_file_header(headers, model_id, log_rec, comman_log_line_obj)
        if skip_header:
            raise UserError(_("The Header of this report must be in English Language, "
                              "Please contact Emipro Support for further Assistance."))
        for row in reader:
            if 'fulfilment-channel' in row.keys():
                fulfillment_type = self.get_fulfillment_type(row.get('fulfilment-channel', ''))
            else:
                fulfillment_type = self.get_fulfillment_type(row.get('fulfillment-channel', ''))

            seller_sku = row.get('seller-sku', '').strip()
            # changed part: add company_id condition
            odoo_product_id = product_obj.search(
                [('company_id', '=', self.instance_id.company_id.id), '|', ('default_code', '=ilike', seller_sku),
                 ('barcode', '=ilike', seller_sku)], limit=1)
            # end of changed part

            amazon_product_id = amazon_product_ept_obj.search_amazon_product( \
                self.instance_id.id, seller_sku, fulfillment_by=fulfillment_type)

            if not amazon_product_id and not odoo_product_id:
                # changed part: add instance_id condition
                amazon_product = amazon_product_ept_obj.with_context(active_test=False).search(
                    [('instance_id', '=', self.instance_id.id), ('seller_sku', '=', seller_sku)], limit=1)
                # end of changed part
                odoo_product_id = amazon_product.product_id

            if amazon_product_id:
                self.create_or_update_amazon_product_ept(amazon_product_id,
                                                         amazon_product_id.product_id.id,
                                                         fulfillment_type, row)
                if self.update_price_in_pricelist:
                    price_list_id.set_product_price_ept(amazon_product_id.product_id.id,
                                                        float(row.get('price')))
            else:
                self.create_odoo_or_amazon_product_ept(odoo_product_id, fulfillment_type, row, log_rec)

        if not log_rec.log_lines:
            log_rec.unlink()
        self.write({'state': 'processed'})
        return True

    def create_odoo_or_amazon_product_ept(self, odoo_product_id, fulfillment_type, row, log_rec):
        """
        SRN-57
        Override: add company_id to newly created product
        """
        product_obj = self.env['product.product']
        comman_log_line_obj = self.env['common.log.lines.ept']
        model_id = comman_log_line_obj.get_model_id('product.product')
        created_product = False
        seller_sku = row.get('seller-sku', '').strip()

        price_list_id = self.instance_id.pricelist_id
        if odoo_product_id:
            self.create_or_update_amazon_product_ept(False, odoo_product_id, fulfillment_type, row)
            if self.update_price_in_pricelist:
                price_list_id.set_product_price_ept(odoo_product_id.id, float(row.get('price')))
        else:
            if self.auto_create_product:
                if not row.get('item-name'):
                    message = """ Line Skipped due to product name not found of seller sku %s || Instance %s
                    """ % (seller_sku, self.instance_id.name)
                else:
                    created_product = product_obj.create(
                        {'default_code': seller_sku,
                         'name': row.get('item-name'),
                         'type': 'product',
                         # changed part
                         'company_id': self.instance_id.company_id.id
                         # end of changed part
                         })
                    self.create_or_update_amazon_product_ept(False, created_product, fulfillment_type, row)
                    message = """ Product created for seller sku %s || Instance %s """ % (
                        seller_sku, self.instance_id.name)
                    if self.update_price_in_pricelist:
                        price_list_id.set_product_price_ept(created_product.id, float(row.get('price')))

            else:
                message = """ Line Skipped due to product not found seller sku %s || Instance %s
                """ % (seller_sku, self.instance_id.name)
            comman_log_line_obj.amazon_create_product_log_line(
                message, model_id, created_product, seller_sku, fulfillment_type, log_rec, row.get('item-name'))
        return True