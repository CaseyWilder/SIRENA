from odoo import http
from odoo.http import request
from odoo.addons.woo_commerce_ept.controllers.main import Webhook


class CustomWebhook(Webhook):

    @http.route(["/update_coupon_webhook_odoo", "/restore_coupon_webhook_odoo"], csrf=False, auth="public", type="json")
    def update_coupon_webhook(self):
        """
        SRN-92
        Inherit: check if restore_coupon_webhook_odoo then active = True
        :return:
        """
        result = super(CustomWebhook, self).update_coupon_webhook()

        res, instance = self.get_basic_info()
        if not res:
            return
        if request.httprequest.path.split('/')[1] == "restore_coupon_webhook_odoo":
            woo_coupon = request.env["woo.coupons.ept"].sudo().with_context(active_test=False).search(["&", "|", ('coupon_id', '=', res.get("id")),
                                                                       ('code', '=', res.get("code")),
                                                                       ('woo_instance_id', '=', instance.id)], limit=1)
            if woo_coupon and instance.active:
                woo_coupon.write({'active': True})

        return result

