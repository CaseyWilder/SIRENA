# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from dateutil import parser

from odoo import api, fields, models, tools, _
from odoo.exceptions import UserError, ValidationError
from odoo.addons.novobi_shipping_account.utils.tracking_url import guess_carrier
from odoo.addons.novobi_shipping_account.models.stock_picking import Picking

SHIPPING_OPTIONS = [
    ('option1', 'Shipping Option 1'),
    ('option2', 'Shipping Option 2')
]

LABEL_STATUS = [
    ('1', 'Shipping Option 1 label created'),
    ('2', 'Shipping Option 2 label created'),
    ('3', 'Both labels created')
]


def button_validate(self):
    """
    Change self.is_create_label to self.label_status to check if no label has been created
    """
    self.ensure_one()

    if self.picking_type_code != 'outgoing':
        return super(Picking, self).button_validate()

    self = self.sudo()

    open_update_done_quantities_form = self.check_open_update_done_quantities_form('confirm_create_shipping_label')
    if open_update_done_quantities_form:
        return open_update_done_quantities_form

    if not self.label_status and 'is_confirm_wiz' not in self.env.context:
        wiz = self.env['confirm.create.shipping.label'].create({'picking_id': self.id})
        return {
            'name': _('Confirmation'),
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'confirm.create.shipping.label',
            'views': [(False, 'form')],
            'view_id': False,
            'target': 'new',
            'res_id': wiz.id,
            'context': self.env.context,
        }

    res = super(Picking, self).button_validate()
    return res

Picking.button_validate = button_validate

class StockPicking(models.Model):
    _inherit = 'stock.picking'

    mso_country_code = fields.Char(related='company_id.country_id.code')
    shipping_options = fields.Selection(SHIPPING_OPTIONS, string='Create Shipping Label Options', copy=False, default=lambda self: self.default_shipping_options())
    label_status = fields.Selection(LABEL_STATUS, string='Keep track label status of the DO', copy=False, compute='_compute_label_status')
    is_void_first_label = fields.Boolean(string='Shipping Option 1', copy=False)
    is_void_second_label = fields.Boolean(string='Shipping Option 2', copy=False)

    # These fields are used to save the first option's settings after create label for option 1
    first_option_package_weight = fields.Float(string='To save first option package shipping weight', copy=False)
    first_option_packaging_id = fields.Many2one('product.packaging', string='To save first option packaging type', copy=False)
    first_option_delivery_carrier_id = fields.Many2one('delivery.carrier', string="To save first option shipping service", domain="[('shipping_account_id.id', '=', shipping_account_id)]", copy=False)
    first_option_handling_fee = fields.Float(string='To save first option handling fee', copy=False)
    first_option_shipping_date = fields.Date(string='To save first option shipping date', copy=False)

    ###########################
    # Shipping Option 2 fields
    ###########################

    # tracking ref
    # shipping service

    second_is_create_label = fields.Boolean(string='Is second shipping label created?', default=False, copy=False)
    second_carrier_tracking_ref = fields.Char(string='Tracking Number', copy=False)
    second_delivery_carrier_id = fields.Many2one('delivery.carrier', string="Shipping Service",
                                                 domain="[('shipping_account_id.id', '=', shipping_account_id)]", copy=False)
    second_default_packaging_id = fields.Many2one('product.packaging',
                                                  string='Package Type',
                                                  domain="[('is_custom', '=', True)]",
                                                  copy=False)
    second_package_size_length = fields.Float('Package Size Length', digits=(16, 2), copy=False,
                                              help='Package Length (in inches)')
    second_package_size_width = fields.Float('Package Size Width', digits=(16, 2), copy=False,
                                             help='Package Width (in inches)')
    second_package_size_height = fields.Float('Package Size Height', digits=(16, 2), copy=False,
                                              help='Package Height (in inches)')
    second_package_shipping_weight = fields.Float(help='Package Shipping Weight (in pounds)',
                                                  copy=False)
    second_handling_fee = fields.Monetary(string='Handling Charges', help='Handling Charges')
    second_shipping_date = fields.Date(string='Ship Date', copy=False)
    second_fedex_shipping_confirmation = fields.Selection(selection=[('SERVICE_DEFAULT', 'Service Default'),
                                                              ('NO_SIGNATURE_REQUIRED', 'No Signature Required'),
                                                              ('ADULT', 'Adult Signature Required'),
                                                              ('DIRECT', 'Direct Signature Required'),
                                                              ('INDIRECT', 'Indirect Signature Required')],
                                                          default='SERVICE_DEFAULT',
                                                          help='Confirmation')

    @api.onchange('shipping_options')
    def _onchange_shipping_options(self):
        """
        Prevents the user from switching to Shipping Option that already has a shipping label created.
        """
        if self.shipping_options == 'option1' and self.label_status == '1':
            raise UserError('There has already been a shipping label for Shipping Option 1, please choose Shipping Option 2 instead!')
        elif self.shipping_options == 'option2' and self.label_status == '2':
            raise UserError('There has already been a shipping label for Shipping Option 2, please choose Shipping Option 1 instead!')

    @api.depends('is_create_label', 'second_is_create_label')
    def _compute_label_status(self):
        """
        Updates stock.picking's label status:
        - False: no label has been created.
        - '1': has shipping label for Shipping Option 1.
        - '2': has shipping label for Shipping Option 2.
        - '3': has shipping labels for both options.
        """
        for record in self:
            is_create_label = 1 if record.is_create_label else 0
            second_is_create_label = 2 if record.second_is_create_label else 0
            label_status = is_create_label + second_is_create_label
            record.label_status = label_status and str(label_status) or False

    def default_shipping_options(self):
        """
        Used to compute default shipping option when opening the Create Label form:
        - If there has been no shipping label created, default shipping option is Shipping Option 1.
        - If there has been a shipping label for Shipping Option 2, default shipping option is Shipping Option 1.
        - If there has been a shipping label for Shipping Option 1, default shipping option is Shipping Option 2.
        """
        if not self.label_status:
            self.shipping_options = 'option1'
            return

        if self.label_status == '2':
            self.shipping_options = 'option1'
            return

        if self.label_status == '1':
            self.shipping_options = 'option2'

    @api.onchange('second_shipping_date')
    def _onchange_second_shipping_date(self):
        """
        Option 1's shipping_date counterpart method.
        """
        if self.second_shipping_date and self.second_shipping_date < fields.Date.today() and 'no_check' not in self.env.context:
            return dict(warning={
                'title': _('Invalid Ship date'),
                'message': _('Ship Date must be greater or equal today.')
            })

    @api.onchange('second_default_packaging_id')
    def _onchange_second_default_packaging_id(self):
        """
        Option 1's default_packaging_id counterpart method.
        """
        self.ensure_one()
        if self.second_default_packaging_id.is_custom:
            self.update({
                'second_package_size_length': self.second_default_packaging_id.length,
                'second_package_size_width': self.second_default_packaging_id.width,
                'second_package_size_height': self.second_default_packaging_id.height,
            })

    def _check_shipping_date(self):
        if self.shipping_options == 'option1':
            super()._check_shipping_date()
        else:
            if any(r.second_shipping_date and r.second_shipping_date < fields.Date.today() for r in self):
                raise UserError(_('Ship Date must be greater or equal today.'))

    @api.onchange('partner_id', 'location_id', 'move_ids_without_package')
    def _onchange_partner_and_location(self):
        self.ensure_one()
        if self.label_status:  # [SRN-99] Switch from checking only is_create_label to check if there is any shipping label using label_status.
            self.is_change_info = True
            self.is_change_info_message_removed = False

    def second_open_website_url(self):
        """
        Smart button "Tracking 2"
        """
        self.ensure_one()
        match = guess_carrier(self.second_carrier_tracking_ref)
        if not match:
            raise UserError(_("Your delivery method has no redirect on courier provider's website to track this order."))
        else:
            return {
                'type': 'ir.actions.act_url',
                'name': "Shipment Tracking Page",
                'target': 'new',
                'url': match.url,
            }

    def create_custom_package_type(self):
        """
        Only create new custom package type when the selecting shipping option is Shipping Option 1.
        """
        self.ensure_one()
        if self.shipping_options == 'option1':
            super().create_custom_package_type()

    @api.model
    def _check_package_shipping_weight(self):
        if self.shipping_options == 'option1':
            super()._check_package_shipping_weight()
        else:
            if any(r.picking_type_code == 'outgoing' and r.second_package_shipping_weight <= 0 for r in self):
                raise UserError(_('Weight for Shipping must be greater than 0.'))

    @api.model
    def _reset_label_fields(self):
        """
        Rewrite method to reset fields based on the selecting shipping option (used when voiding labels).
        """
        vals = {
            'shipping_cost': 0.0,
            'shipping_cost_without_discounts': 0.0,
            # 'handling_fee': 0.0,
            'no_shipping_cost': False,
            'insurance_cost': 0.0,
            'no_insurance_cost': False,
            'carrier_price': 0.0,
            # 'package_size_length': 0,
            # 'package_size_width': 0,
            # 'package_size_height': 0,
            'estimated_shipping_rate': 0.0,
            # 'provider': False,
            'shipping_insurance': 'none',
            'shipping_insurance_amount': False,
            'shipping_estimated_date': False,
            # 'shipping_account_id': False,
            # 'delivery_carrier_id': False,
            # 'shipping_date': False,
            # 'carrier_tracking_ref': False,
            'carrier_tracking_url': False,
            'carrier_id': False,
            # 'default_packaging_id': False,
            'usps_is_first_class': False,
            'usps_first_class_mail_type': False,
            'usps_container': False,
            'custom_packaging_name': False,

            # Other Shipping Information
            'shipping_non_machinable': False,
            'shipping_require_additional_handling': False,
            'shipping_change_billing': False,
            'shipping_include_alcohol': False,
            'shipping_not_notify_marketplace': False,
            'shipping_include_return_label': False,
            'shipping_bill_duty_and_tax': False,
            'shipping_include_dry_ice': False,
            'shipping_saturday_delivery': False,
            'shipping_cod': False,
            'shipping_optional_signature': False,

            # Additional data for other shipping information
            'shipping_dry_ice_weight_in_oz': False,
            'shipping_cod_amount': False,
            'shipping_customer_account': False,
            'shipping_customer_zipcode': False,
            'shipping_cod_payment_type': False,

            # Remove Flags
            'is_change_info': False,
            # 'is_mul_packages': False,
            # 'is_create_label': False,
            "is_save_custom_package": False,
        }
        if self.is_void_first_label:
            vals.update({
                'default_packaging_id': False,
                'package_size_length': 0,
                'package_size_width': 0,
                'package_size_height': 0,
                'handling_fee': 0.0,
                'delivery_carrier_id': self.shipping_account_id.delivery_carrier_ids[0].id,
                'shipping_date': False,
                'carrier_tracking_ref': False,
                'is_mul_packages': False,
                'is_create_label': False,
                'fedex_shipping_confirmation': False
            })
        if self.is_void_second_label:
            vals.update({
                'second_default_packaging_id': False,
                'second_package_size_length': 0,
                'second_package_size_width': 0,
                'second_package_size_height': 0,
                'second_handling_fee': 0.0,
                'second_delivery_carrier_id': self.shipping_account_id.delivery_carrier_ids[0].id,
                'second_shipping_date': False,
                'second_carrier_tracking_ref': False,
                'second_is_create_label': False,
                'second_fedex_shipping_confirmation': False
            })
        return vals

    def reset_label_fields(self):
        self.sudo().write(self._reset_label_fields())
        if self.is_void_first_label and self.picking_package_ids:  # Only unlink the MPS table if void Shipping Option 1's label
            self.sudo().picking_package_ids.unlink()

    def open_create_label_form(self):
        res = super().open_create_label_form()
        self.default_shipping_options()
        self.second_shipping_date = fields.Datetime.to_string(max(self.scheduled_date, fields.Datetime.now()))

        # Recover saved fields for Option 1 (these fields were modified when calling super().open_create_label_form() above)
        if self.shipping_options == 'option2':
            self.update({
                'delivery_carrier_id': self.first_option_delivery_carrier_id,
                'default_packaging_id': self.first_option_packaging_id,
                'package_shipping_weight': self.first_option_package_weight,
                'handling_fee': self.first_option_handling_fee,
                'shipping_date': self.first_option_shipping_date
            })
            self._onchange_default_packaging_id()

        return res

    def action_create_label(self):
        self.ensure_one()
        self = self.sudo()
        self._check_package_shipping_weight()
        self._check_shipping_date()

        if self.shipping_options == 'option1' and self.is_save_custom_package:
            self.create_custom_package_type()

        shipping_options = {
            'shipping_non_machinable': self.shipping_non_machinable,
            'shipping_require_additional_handling': self.shipping_require_additional_handling,
            'shipping_change_billing': self.shipping_change_billing,
            'shipping_include_alcohol': self.shipping_include_alcohol,
            'shipping_not_notify_marketplace': self.shipping_not_notify_marketplace
        }
        label_options = {
            'shipping_include_return_label': self.shipping_include_return_label,
            'shipping_bill_duty_and_tax': self.shipping_bill_duty_and_tax,
            'shipping_include_dry_ice': self.shipping_include_dry_ice,
        }
        delivery_options = {
            'shipping_saturday_delivery': self.shipping_saturday_delivery,
            'shipping_cod': self.shipping_cod
        }
        insurance_options = {
            'insurance_provider': self.shipping_insurance,
            'insurance_amount': self.shipping_insurance_amount
        }

        if self.shipping_options == 'option1':
            res = self.delivery_carrier_id.create_shipment_label(picking=self,
                                                                 product_packaging=self.default_packaging_id,
                                                                 package_length=self.package_size_length,
                                                                 package_width=self.package_size_width,
                                                                 package_height=self.package_size_height,
                                                                 weight=self.package_shipping_weight,
                                                                 pickup_date=self.shipping_date,
                                                                 shipping_options=shipping_options,
                                                                 label_options=label_options,
                                                                 delivery_options=delivery_options,
                                                                 insurance_options=insurance_options)
        else:
            res = self.second_delivery_carrier_id.create_shipment_label(picking=self,
                                                                        product_packaging=self.second_default_packaging_id,
                                                                        package_length=self.second_package_size_length,
                                                                        package_width=self.second_package_size_width,
                                                                        package_height=self.second_package_size_height,
                                                                        weight=self.second_package_shipping_weight,
                                                                        pickup_date=self.second_shipping_date,
                                                                        shipping_options=shipping_options,
                                                                        label_options=label_options,
                                                                        delivery_options=delivery_options,
                                                                        insurance_options=insurance_options)

        if 'error_message' in res and res.get('error_message'):
            raise UserError(_("Error: %s") % res['error_message'])

        estimated_date = res.get('estimated_date')
        try:
            if isinstance(estimated_date, str):
                estimated_datetime = parser.parse(estimated_date)
                estimated_date = f'{estimated_datetime:%m/%d/%Y}'
        except ValueError:
            pass

        # Shipping cost = -1 means that Carrier does not return any data about shipping cost
        # Shipping cost = N/A will display in UI
        shipping_cost = 0 if not res['price'] else res['price']
        shipping_cost_without_discounts = res.get('price_without_discounts', 0.0)
        no_shipping_cost = True if not res['price'] else False

        vals = {
            # 'carrier_id': self.delivery_carrier_id.id,
            # 'is_create_label': True,
            'shipping_cost': shipping_cost,
            'shipping_cost_without_discounts': shipping_cost_without_discounts,
            'shipping_estimated_date': estimated_date or 'N/A',
            # 'carrier_tracking_ref': res['carrier_tracking_ref'],
            'no_shipping_cost': no_shipping_cost
        }

        # Update fields according to their selected shipping option when creating label.
        if self.shipping_options == 'option1':
            vals.update({
                'is_create_label': True,
                'carrier_tracking_ref': res['carrier_tracking_ref'],
                'first_option_package_weight': self.package_shipping_weight,
                'first_option_delivery_carrier_id': self.delivery_carrier_id,
                'first_option_packaging_id': self.default_packaging_id,
                'first_option_handling_fee': self.handling_fee,
                'first_option_shipping_date': self.shipping_date
            })
        else:
            vals.update({
                'second_is_create_label': True,
                'second_carrier_tracking_ref': res['carrier_tracking_ref']
            })

        if 'package_carrier_tracking_ref' in res:
            pp_ls = zip(self.picking_package_ids.ids, res['package_carrier_tracking_ref'])
            vals.update({
                'picking_package_ids': [(1, ppl[0], {'carrier_tracking_ref': ppl[1]}) for ppl in pp_ls]
            })

        if 'insurance_cost' in res:
            # Insurance cost = -1 means that Carrier does not return any data about insurance
            # Insurance cost = N/A will display in UI
            insurance_cost = 0 if not res['insurance_cost'] else res['insurance_cost']
            no_insurance_cost = True if not res['insurance_cost'] else False
            vals.update({'insurance_cost': insurance_cost, 'no_insurance_cost': no_insurance_cost})

        # Force update to channel if possible
        context = dict(self.env.context)
        self.with_context(context).update(vals)

        if self.env.context.get('validate_do'):
            return self.with_context(context).button_validate()

        return True

    def button_void_label(self):
        self.ensure_one()
        self = self.sudo()
        if not self.label_status:
            return True

        # Set for_syncing to True in order to avoid updating this picking to channel
        # Just need to update this once in reset label fields call
        if self.is_void_first_label and self.provider == 'fedex':
            res = self.delivery_carrier_id.fedex_void_label(picking=self, master_tracking_id=self.carrier_tracking_ref)
            if 'error_message' in res and res.get('error_message'):
                raise UserError(_('Void label error on the 1st shipping option: ' + str(res['error_message'])))
        if self.is_void_second_label and self.provider == 'fedex':
            res = self.second_delivery_carrier_id.fedex_void_label(picking=self, master_tracking_id=self.second_carrier_tracking_ref)
            if 'error_message' in res and res.get('error_message'):
                raise UserError(_('Void label error on the 2nd shipping option: ' + str(res['error_message'])))
        if self.provider != 'fedex':
            res = self.delivery_carrier_id.void_label(picking=self)
            if 'error_message' in res and res.get('error_message'):
                raise UserError(_('Void label error on the 1st shipping option: ' + str(res['error_message'])))

        self.reset_label_fields()
        return True

    def get_carrier_rate(self):
        self.ensure_one()
        self = self.sudo()
        self._check_package_shipping_weight()
        if self.shipping_options == 'option1':
            res = self.delivery_carrier_id.get_rate_and_delivery_time(picking=self,
                                                                      product_packaging=self.default_packaging_id,
                                                                      package_length=self.package_size_length,
                                                                      package_width=self.package_size_width,
                                                                      package_height=self.package_size_height,
                                                                      weight=self.package_shipping_weight,
                                                                      pickup_date=self.shipping_date,
                                                                      shipping_options="",
                                                                      insurance_amount=self.shipping_insurance_amount)
        else:
            res = self.second_delivery_carrier_id.get_rate_and_delivery_time(picking=self,
                                                                             product_packaging=self.second_default_packaging_id,
                                                                             package_length=self.second_package_size_length,
                                                                             package_width=self.second_package_size_width,
                                                                             package_height=self.second_package_size_height,
                                                                             weight=self.second_package_shipping_weight,
                                                                             pickup_date=self.second_shipping_date,
                                                                             shipping_options="",
                                                                             insurance_amount=self.shipping_insurance_amount)
        return res

    def action_cancel(self):
        for record in self.filtered(lambda r: r.is_create_label):
            record.is_void_first_label = True
            record.button_void_label()
        for record in self.filtered(lambda r: r.second_is_create_label):
            record.is_void_second_label = True
            record.button_void_label()
        return super(StockPicking, self).action_cancel()

    def write(self, vals):
        if 'create_label' in self.env.context:
            return super(StockPicking, self).write(vals)
        if 'move_lines' in vals and self.label_status:  # Switch label_status to check if there has been any shipping label created
            # Raise Warning when users add or remove move line in Delivery Order
            vals['is_change_info'] = True
            vals['is_change_info_message_removed'] = False

        return super(StockPicking, self).write(vals)

    def open_mso_void_label_wizard(self):
        return {
            'name': _('Confirmation'),
            'view_mode': 'form',
            'res_model': 'mso.void.label',
            'type': 'ir.actions.act_window',
            'context': {
                'default_picking_id': self.id,
            },
            'target': 'new'
        }
