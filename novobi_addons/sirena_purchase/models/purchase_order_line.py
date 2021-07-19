import os
from odoo import models, fields, api


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    # Expose these product.template fields so that they could be displayed in report.
    part_name_in_chinese = fields.Char(string="Part Name in Chinese",
                                       related='product_id.product_tmpl_id.part_name_in_chinese')
    drawing_number = fields.Char(string="Drawing Number",
                                 related='product_id.product_tmpl_id.drawing_number')
    substance = fields.Char(string="Substance",
                            related='product_id.product_tmpl_id.substance')
    parts_spec_color = fields.Char(string="Parts Spec / Color",
                                   related='product_id.product_tmpl_id.parts_spec_color')
    part_code = fields.Char(string="Part Code",
                            related='product_id.product_tmpl_id.part_code')
    product_image_1920 = fields.Image(max_width=80, max_height=50, related='product_id.image_1920')

    @api.model
    def install_cn_font(self):
        # Potential risks:
        # - Packages could be unregistered and replaced with harmful packages.
        # - Roughly 25 MB of storage will be consumed.
        os.system("apt-get install -y ttf-wqy-microhei ttf-wqy-zenhei")
