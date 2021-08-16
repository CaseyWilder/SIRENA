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
