import math
import html
import time
from odoo import models, fields, api


class AmazonProductEpt(models.Model):
    _inherit = "amazon.product.ept"

    def prepare_export_stock_level_dict_operation(self, amazon_product, instance, actual_stock, message_information,
                                                  message_id):
        """
        SRN-54
        Override: convert fulfillment_latency from float to int
        """
        seller_sku = html.escape(amazon_product['seller_sku'])
        stock = self.stock_ept_calculation(actual_stock,
                                           amazon_product['fix_stock_type'],
                                           amazon_product['fix_stock_value'])
        if amazon_product['allow_package_qty']:
            asin_qty = amazon_product['asin_qty']
            stock = math.floor(stock / asin_qty) if asin_qty > 0.0 else stock

        stock = 0 if int(stock) < 1 else int(stock)
        fullfillment_latency = amazon_product.product_id.sale_delay or amazon_product['fulfillment_latency'] or \
                               instance.seller_id.fulfillment_latency
        message_information += """<Message><MessageID>%s</MessageID>
                <OperationType>Update</OperationType>
                <Inventory><SKU>%s</SKU><Quantity>%s</Quantity><FulfillmentLatency>%s</FulfillmentLatency></Inventory>
                </Message>""" % (message_id, seller_sku, stock, int(fullfillment_latency))
        return message_information

    def process_amazon_update_price_result(self, instance, data, results):
        """
        SRN-55
        Override: remove error_in_export_price
        """
        amazon_feed_submit_history = self.env['feed.submission.history']

        if results.get('FeedSubmissionInfo', {}).get('FeedSubmissionId', \
                                                     {}).get('value', False):
            last_feed_submission_id = results.get('FeedSubmissionInfo', {}).get( \
                'FeedSubmissionId', {}).get('value', False)
            vals = {'message': data, 'feed_result_id': last_feed_submission_id,
                    'feed_submit_date': time.strftime("%Y-%m-%d %H:%M:%S"),
                    'instance_id': instance.id, 'user_id': self._uid,
                    'feed_type': 'export_price',
                    'seller_id': instance.seller_id.id}
            amazon_feed_submit_history.create(vals)
        return True
