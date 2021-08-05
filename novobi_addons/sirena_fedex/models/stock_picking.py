from odoo import models, fields, api


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def open_create_label_form(self):
        result = super().open_create_label_form()

        fedex = self.env['shipping.account'].search([('provider', '=', 'fedex')], limit=1)

        if self.env.user.company_id.country_id.code != 'US' or not fedex:
            return result
        else:
            self.shipping_account_id = fedex

            if self.partner_id.address_classification == 'RESIDENTIAL':
                for dc_id in fedex.delivery_carrier_ids.ids:
                    delivery_carrier = self.env['delivery.carrier'].search([('id', '=', dc_id)])
                    if delivery_carrier.fedex_service_type == 'GROUND_HOME_DELIVERY':
                        self.delivery_carrier_id = delivery_carrier
                        self.is_residential_address = True
            else:
                for dc_id in fedex.delivery_carrier_ids.ids:
                    delivery_carrier = self.env['delivery.carrier'].search([('id', '=', dc_id)])
                    if delivery_carrier.fedex_service_type == 'FEDEX_GROUND':
                        self.delivery_carrier_id = delivery_carrier
                        self.is_residential_address = False

            return result
