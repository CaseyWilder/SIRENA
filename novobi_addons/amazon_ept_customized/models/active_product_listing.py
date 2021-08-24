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
        Override: Apply product sku mapping
        """
        self.ensure_one()
        if not self.attachment_id:
            raise UserError(_("There is no any report are attached with this record."))
        if not self.instance_id:
            raise UserError(_("Instance not found "))
        if not self.instance_id.pricelist_id:
            raise UserError(_("Please configure Pricelist in Amazon Marketplace"))

        amazon_product_ept_obj = self.env['amazon.product.ept']
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
            # changed part: search in product mapping
            product_mapping_obj = self.env['amazon.product.mapping']
            product_mapping = product_mapping_obj.search([('amz_sku', '=', seller_sku), ('instance_id', '=', self.instance_id.id)], limit=1)
            odoo_product_id = product_mapping.odoo_product_id
            amazon_product_id = product_mapping.amazon_product_id
            # end of changed part

            if amazon_product_id:
                self.create_or_update_amazon_product_ept(amazon_product_id,
                                                         odoo_product_id,
                                                         fulfillment_type, row)
                if self.update_price_in_pricelist:
                    price_list_id.set_product_price_ept(amazon_product_id.product_id.id,
                                                        float(row.get('price')))
            else:
                # changed part: if product_mapping doesn't exist, check if odoo product exists before creating new one
                if not product_mapping:
                    odoo_product_id = self.env['product.product'].search([('default_code', '=', seller_sku)], limit=1)
                # end of changed part
                self.create_odoo_or_amazon_product_ept(odoo_product_id, fulfillment_type, row, log_rec)
            # changed part: update/create product mapping
            if not amazon_product_id:
                new_amazon_product_id = amazon_product_ept_obj.search([('seller_sku', '=', seller_sku), ('instance_id', '=', self.instance_id.id)], limit=1)
            if product_mapping and not amazon_product_id:
                product_mapping.amazon_product_id = new_amazon_product_id
            if not product_mapping and new_amazon_product_id:
                product_mapping_obj.create({
                    'odoo_product_id': new_amazon_product_id.product_id.id,
                    'amazon_product_id': new_amazon_product_id.id,
                    'instance_id': new_amazon_product_id.instance_id.id
                })
            # end of changed part

        if not log_rec.log_lines:
            log_rec.unlink()
        self.write({'state': 'processed'})
        return True
