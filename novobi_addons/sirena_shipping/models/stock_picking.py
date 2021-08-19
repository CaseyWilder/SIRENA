from odoo import models, fields, api


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def open_create_label_form(self):
        result = super().open_create_label_form()

        if self.company_id.country_id.code == 'US' and isinstance(result, dict) and result.get('res_model') == 'stock.picking':
            fedex = self.env['shipping.account'].search([('provider', '=', 'fedex')], limit=1)
            if not fedex:
                return result

            carriers = fedex.delivery_carrier_ids

            if self.partner_id.address_classification == 'RESIDENTIAL':
                delivery_carrier = carriers.filtered(lambda r: r.fedex_service_type == 'GROUND_HOME_DELIVERY')
                is_residential_address = True if delivery_carrier else self.is_residential_address
            else:
                delivery_carrier = carriers.filtered(lambda r: r.fedex_service_type == 'FEDEX_GROUND')
                is_residential_address = False if delivery_carrier else self.is_residential_address

            delivery_carrier_id = delivery_carrier and delivery_carrier[0].id
            self.update({
                'shipping_account_id': fedex.id,
                'delivery_carrier_id': delivery_carrier_id,
                'is_residential_address': is_residential_address
            })
        elif self.company_id.country_id.code == 'CA' and isinstance(result, dict) and result.get('res_model') == 'stock.picking':
            ups = self.env['shipping.account'].search([('provider', '=', 'ups')], limit=1)
            if not ups:
                return result

            delivery_carrier_id = ups.delivery_carrier_ids.filtered(lambda r: r.ups_default_service_type == '11')
            self.update({
                'shipping_account_id': ups.id,
                'delivery_carrier_id': delivery_carrier_id,
            })
        else:
            return result

        if delivery_carrier_id:
            self.onchange_delivery_carrier_id()
            if self.default_packaging_id:
                self._onchange_default_packaging_id()

        return result
