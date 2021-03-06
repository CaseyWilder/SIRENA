from odoo import models, fields, api


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    default_packaging_id = fields.Many2one(domain=[('is_custom', '=', True)])

    def check_for_one_product_or_bundle(self):
        product_ids = self.move_line_ids.mapped('product_id')
        if len(product_ids) == 1:
            return product_ids

        bom_ids = self.move_ids_without_package.mapped('bom_line_id').mapped('bom_id')
        if len(bom_ids) == 1:
            return bom_ids.product_tmpl_id
        return False

    def calculate_weight_based_on_quantity_column(self, shipping_account):
        if not shipping_account:
            return

        if shipping_account.stock_quantity_column and shipping_account.stock_quantity_column == 'done':
            return

        total_move_weight = 0
        for ml in self.move_lines:
            # 1 ounce = 0.0625 pound
            if hasattr(ml.product_id, 'weight_in_oz') and ml.product_id.weight_in_oz != 0:
                product_weight_in_lbs = ml.product_id.weight_in_oz * 0.0625
            else:
                weight_uom_lbs_id = self.env.ref('uom.product_uom_lb')
                weight_uom_system_id = self.env['product.template']._get_weight_uom_id_from_ir_config_parameter()

                product_weight_in_lbs = weight_uom_system_id._compute_quantity(ml.product_id.weight,
                                                                               weight_uom_lbs_id, round=False)
            if shipping_account.stock_quantity_column == 'demand':  # Demand quantity
                total_product_weight = product_weight_in_lbs * ml.product_uom_qty
            else:  # Reserve quantity
                total_product_weight = product_weight_in_lbs * ml.forecast_availability
            total_move_weight += total_product_weight
        self.package_shipping_weight = round(total_move_weight, 3)

    def open_create_label_form(self):
        result = super().open_create_label_form()

        if self.company_id.country_id.code == 'US' and isinstance(result, dict) and result.get('res_model') == 'stock.picking':
            fedex = self.env['shipping.account'].search([('provider', '=', 'fedex')], limit=1)
            if not fedex:
                return result

            self.calculate_weight_based_on_quantity_column(shipping_account=fedex)

            carriers = fedex.delivery_carrier_ids
            one_product_or_bundle = self.check_for_one_product_or_bundle()

            if self.partner_id.address_classification == 'RESIDENTIAL':
                delivery_carrier = carriers.filtered(lambda r: r.fedex_service_type == 'GROUND_HOME_DELIVERY')
                is_residential_address = True if delivery_carrier else self.is_residential_address
            else:
                delivery_carrier = carriers.filtered(lambda r: r.fedex_service_type == 'FEDEX_GROUND')
                is_residential_address = False if delivery_carrier else self.is_residential_address

            if one_product_or_bundle and one_product_or_bundle.delivery_carrier_id == 'SMART_POST':
                delivery_carrier = carriers.filtered(lambda r: r.fedex_service_type == 'SMART_POST')
                is_residential_address = self.is_residential_address

            delivery_carrier_id = delivery_carrier and delivery_carrier[0].id
            vals = {
                'shipping_account_id': fedex.id,
                'is_residential_address': is_residential_address
            }
            if delivery_carrier_id:
                vals.update({'delivery_carrier_id': delivery_carrier_id})
            self.update(vals)
        elif self.company_id.country_id.code == 'CA' and isinstance(result, dict) and result.get('res_model') == 'stock.picking':
            ups = self.env['shipping.account'].search([('provider', '=', 'ups')], limit=1)
            if not ups:
                return result

            self.calculate_weight_based_on_quantity_column(shipping_account=ups)

            delivery_carrier_id = ups.delivery_carrier_ids.filtered(lambda r: r.ups_default_service_type == '11')
            if delivery_carrier_id:
                self.update({
                    'shipping_account_id': ups.id,
                    'delivery_carrier_id': delivery_carrier_id,
                })
            else:
                self.shipping_account_id = ups.id
        else:
            return result

        if delivery_carrier_id:
            self.onchange_delivery_carrier_id()
            if self.default_packaging_id:
                self._onchange_default_packaging_id()

        return result

    def check_open_update_done_quantities_form(self, callback):
        """
        Inherit: add conditions not to show update qty form
        """
        if self.company_id.country_id.code == 'US':
            fedex = self.env['shipping.account'].search([('provider', '=', 'fedex')], limit=1)
            if fedex and fedex.stock_quantity_column != 'done':
                return False
        elif self.company_id.country_id.code == 'CA':
            ups = self.env['shipping.account'].search([('provider', '=', 'ups')], limit=1)
            if ups and ups.stock_quantity_column != 'done':
                return False
        return super(StockPicking, self).check_open_update_done_quantities_form(callback)
