import logging
from datetime import datetime
from odoo import models, fields, api, _

_logger = logging.getLogger("WooCommerce")


class WooProductTemplateEpt(models.Model):

    _inherit = "woo.product.template.ept"


    def simple_product_sync(self, woo_instance, product_response, common_log_book_id, product_queue_id,
                            product_data_queue_line, template_updated, skip_existing_products, order_queue_line):
        """
        Override: Apply product sku mapping
        """
        common_log_line_obj = self.env["common.log.lines.ept"]
        woo_template = odoo_template = sync_category_and_tags = False
        model_id = common_log_line_obj.get_model_id(self._name)
        update_price = woo_instance.sync_price_with_product
        update_images = woo_instance.sync_images_with_product
        template_title = product_response.get("name")
        woo_product_template_id = product_response.get("id")
        product_sku = product_response["sku"]
        variant_price = product_response.get("regular_price") or product_response.get("sale_price") or 0.0
        template_info = self.prepare_template_vals(woo_instance, product_response)

        if order_queue_line:
            sync_category_and_tags = True
        if not product_sku:
            message = """Value of SKU/Internal Reference is not set for product '%s', in the Woocommerce store.""", \
                      template_title
            common_log_line_obj.woo_create_product_log_line(message, model_id,
                                                            product_data_queue_line if not order_queue_line
                                                            else order_queue_line, common_log_book_id)
            _logger.info("Process Failed of Product %s||Queue %s||Reason is %s", woo_product_template_id,
                         product_queue_id, message)
            if not order_queue_line:
                product_data_queue_line.write({"state": "failed", "last_process_date": datetime.now()})
            return False

        # changed part: search in product mapping
        woo_product_obj = self.env['woo.product.product.ept']
        product_mapping_obj = self.env['woo.product.mapping']
        product_mapping = product_mapping_obj.search([('woo_sku', '=', product_sku), ('instance_id', '=', woo_instance.id)], limit=1)
        odoo_product = product_mapping.odoo_product_id
        woo_product = product_mapping.woo_product_id
        # end of changed part

        if woo_product and not odoo_product:
            woo_template = woo_product.woo_template_id
            odoo_product = woo_product.product_id
            if skip_existing_products:
                product_data_queue_line.state = "done"
                return False
        if woo_product:
            woo_template = woo_product.woo_template_id
        if odoo_product:
            odoo_template = odoo_product.product_tmpl_id

        is_importable, message = self.is_product_importable(product_response, odoo_product, woo_product)
        if not is_importable:
            common_log_line_obj.woo_create_product_log_line(message, model_id,
                                                            product_data_queue_line if not order_queue_line else
                                                            order_queue_line, common_log_book_id)
            _logger.info("Process Failed of Product %s||Queue %s||Reason is %s", woo_product_template_id,
                         product_queue_id, message)
            if not order_queue_line:
                product_data_queue_line.state = "failed"
            return False
        variant_info = self.prepare_woo_variant_vals(woo_instance, product_response)
        if not woo_product:
            if not woo_template:
                # changed part: if product_mapping doesn't exist, check if odoo product exists before creating new one
                if not product_mapping:
                    odoo_product = self.env['product.product'].search([('default_code', '=', product_sku)], limit=1)
                    odoo_template = odoo_product.product_tmpl_id
                # end of changed part
                if not odoo_template and woo_instance.auto_import_product:
                    woo_weight = float(product_response.get("weight") or "0.0")
                    weight = self.convert_weight_by_uom(woo_weight, woo_instance, import_process=True)
                    template_vals = {
                        "name": template_title, "type": "product", "default_code": product_response["sku"],
                        "weight": weight, "invoice_policy": "order"
                    }
                    if self.env["ir.config_parameter"].sudo().get_param("woo_commerce_ept.set_sales_description"):
                        template_vals.update({"description_sale": product_response.get("description", ""),
                                              "description": product_response.get("short_description", "")})
                    if product_response["virtual"]:
                        template_vals.update({"type": "service"})
                    odoo_template = self.env["product.template"].create(template_vals)
                    odoo_product = odoo_template.product_variant_ids
                if not odoo_template:
                    message = "%s Template Not found for sku %s in Odoo." % (template_title, product_sku)
                    common_log_line_obj.woo_create_product_log_line(message, model_id,
                                                                    product_data_queue_line if not order_queue_line
                                                                    else order_queue_line, common_log_book_id)
                    _logger.info("Process Failed of Product %s||Queue %s||Reason is %s", woo_product_template_id,
                                 product_queue_id, message)
                    if not order_queue_line:
                        product_data_queue_line.state = "failed"
                    return False

                woo_template_vals = self.prepare_woo_template_vals(template_info, odoo_template.id,
                                                                   sync_category_and_tags, woo_instance,
                                                                   common_log_book_id)
                if product_response["virtual"] and odoo_template.type == 'service':
                    woo_template_vals.update({"is_virtual_product": True})
                    odoo_template.write({"type": "service"})
                woo_template = self.create(woo_template_vals)

            variant_info.update({"product_id": odoo_product.id, "woo_template_id": woo_template.id})
            woo_product = self.env["woo.product.product.ept"].create(variant_info)
        else:
            if not template_updated:
                # param change: woo_template.product_tmpl_id.id -> odoo_template.id
                woo_template_vals = self.prepare_woo_template_vals(template_info, odoo_template,
                                                                   sync_category_and_tags, woo_instance,
                                                                   common_log_book_id)
                woo_template.write(woo_template_vals)
            woo_product.write(variant_info)
        # changed part: update/create product mapping
        woo_product_id = product_mapping.woo_product_id
        if not woo_product_id:
            new_woo_product_id = woo_product_obj.search(
                [('default_code', '=', product_sku), ('woo_instance_id', '=', woo_instance.id)], limit=1)
        if product_mapping and not woo_product_id:
            product_mapping.woo_product_id = new_woo_product_id
        if not product_mapping and new_woo_product_id:
            product_mapping_obj.create({
                'odoo_product_id': new_woo_product_id.product_id.id,
                'woo_product_id': new_woo_product_id.id,
                'instance_id': new_woo_product_id.woo_instance_id.id
            })
        # end of changed part
        if update_price:
            woo_instance.woo_pricelist_id.set_product_price_ept(woo_product.product_id.id, variant_price)
        if update_images and isinstance(product_queue_id, str) and product_queue_id == 'from Order':
            self.update_product_images(product_response["images"], {}, woo_template, woo_product, woo_instance, False)
        if woo_template:
            return woo_template
        return True
