from odoo import api, models, fields, _


class WooProcessImportExport(models.TransientModel):
    _inherit = 'woo.process.import.export'
    _description = "WooCommerce Import/Export Process"

    def update_woo_coupons(self):
        """
        SRN-91
        Override: split coupon_ids to lists of 100 coupon
                because the API is unable to accept more than 100 items for this request.
        """
        coupon_obj = self.env['woo.coupons.ept']
        common_log_book_obj = self.env["common.log.book.ept"]
        model_id = self.env["common.log.lines.ept"].get_model_id("woo.coupons.ept")
        common_log_book_id = common_log_book_obj.woo_create_log_book('export', self.woo_instance_id)

        coupon_ids = self._context.get('active_ids')
        if coupon_ids and self._context.get('process'):
            coupon_ids = coupon_obj.search(
                [('id', 'in', coupon_ids), ('coupon_id', '!=', False), ('exported_in_woo', '=', True)])
        else:
            coupon_ids = coupon_obj.search(
                [('coupon_id', '!=', False), ('woo_instance_id', '=', self.woo_instance_id.id),
                 ('exported_in_woo', '=', True)])

        if coupon_ids:
            # changed part
            coupon_batches = [coupon_ids[i:i + 100] for i in range(0, len(coupon_ids), 100)]
            for coupon_batch in coupon_batches:
                coupon_batch.update_woo_coupons(coupon_ids.woo_instance_id, common_log_book_id, model_id)
