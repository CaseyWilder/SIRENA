# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

import logging
from odoo import api, fields, models, _
from odoo.exceptions import Warning

_logger = logging.getLogger(__name__)


class DeliveryCarrier(models.Model):
    _inherit = 'delivery.carrier'

    shipping_account_id = fields.Many2one('shipping.account', string='Account', ondelete='set null')


class ShippingAccount(models.Model):
    _name = 'shipping.account'
    _description = 'Shipping Account'

    name = fields.Char(string='Name', required=True)
    provider = fields.Selection([('none', 'None')], string='Provider', required=True, default='none')
    active = fields.Boolean(string='Active', default=True)
    active_status = fields.Selection([('active', 'Active'), ('inactive', 'Inactive')],
                                     string='Active Status', compute='_get_active_status')
    delivery_carrier_ids = fields.Many2many('delivery.carrier', string='Services')
    provider_logo_url = fields.Char(compute='_get_provider_logo_url', store=True)

    number_of_services = fields.Integer(string='Number of Services', compute='_get_number_of_services', store=True)
    prod_environment = fields.Boolean("Is Production Environment", help="Set to True if your credentials are certified for production.")
    environment = fields.Selection([('test', 'Test'), ('production', 'Production')],
                                   string='Environment', compute='_get_environment')
    currency_id = fields.Many2one('res.currency', string='Currency', default=lambda self: self.env.company.currency_id)
    debug_logging = fields.Boolean('Debug logging', help='Log requests in order to ease debugging')
    handling_fee = fields.Monetary(string='Handling Charges', help='Handling Charges for each package')

    label_file_type = fields.Selection(selection=[
        ('PDF', 'PDF'),
        ('ZPL', 'ZPL')
    ], string='Label File Type', required=True, default='PDF')

    _sql_constraints = [('unique_name', 'UNIQUE(name)', 'This account name has already existed!\nPlease try another name.')]

    def _get_environment(self):
        for record in self:
            record.environment = 'test' if not record.prod_environment else 'production'

    def toggle_prod_environment(self):
        for c in self:
            c.prod_environment = not c.prod_environment
            c.delivery_carrier_ids.update(dict(prod_environment=c.prod_environment))

    def toggle_debug_logging(self):
        for record in self:
            record.debug_logging = not record.debug_logging
            record.delivery_carrier_ids.update(dict(debug_logging=record.debug_logging))

    def check_connection(self):
        self.ensure_one()
        cust_method_name = '%s_check_connection' % self.provider
        if hasattr(self.env['delivery.carrier'], cust_method_name):
            res = getattr(self.env['delivery.carrier'], cust_method_name)(self)
            if res and res.get('error_message'):
                raise Warning(res.get('error_message'))
            else:
                return {
                    'effect': {
                        'type': 'rainbow_man',
                        'message': _("Everything is correctly set up!"),
                    }
                }
        else:
            raise Warning(_("Connected Fail"))

    def _get_active_status(self):
        for record in self:
            record.active_status = 'active' if record.with_context(active_test=False).active else 'inactive'

    @api.model
    def _get_logo_url(self):
        if self.provider == 'none':
            return ''
        return ''

    @api.depends('provider')
    def _get_provider_logo_url(self):
        for record in self:
            record.provider_logo_url = record._get_logo_url()

    @api.depends('delivery_carrier_ids', 'delivery_carrier_ids.active')
    def _get_number_of_services(self):
        for record in self:
            if record.active:
                record.number_of_services = len(record.delivery_carrier_ids)
            else:
                record.number_of_services = len(record.with_context(active_test=False).delivery_carrier_ids)

    def action_open_settings_form(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id('novobi_shipping_account.action_shipping_account_settings')
        action['name'] = self.name
        action['res_id'] = self.id
        return action

    def action_open_service_list(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id('novobi_shipping_account.action_service_lists')
        action['name'] = self.name
        action['res_id'] = self.id
        return action

    def update_selected_services(self):
        return True

    @api.model
    def _get_credential_fields(self):
        return ['prod_environment', 'active']

    def _create_services(self):
        self.ensure_one()
        custom_method_name = '%s_create_services' % self.provider
        if hasattr(self, custom_method_name):
            getattr(self, custom_method_name)()
        self.delivery_carrier_ids.update(dict(
            prod_environment=self.prod_environment,
            debug_logging=self.debug_logging
        ))

    @api.model
    def _remove_redundant_field(self, provider):
        if provider:
            provider_keys = list(dict(self._fields['provider'].selection).keys())
            remove_fields = []
            for pk in provider_keys:
                if pk == provider:
                    continue
                provider_var = "%s_FIELDS" % pk.upper()
                if hasattr(self, provider_var):
                    remove_fields.extend(getattr(self, provider_var))
            remove_fields = {rf: False for rf in remove_fields}
            return remove_fields
        return {}

    def _update_label_file_type(self):
        custom_method_name = f'_{self.provider}_update_label_file_type'
        if hasattr(self, custom_method_name):
            getattr(self, custom_method_name)()

    @api.model
    def create(self, vals):
        vals.update(self._remove_redundant_field(vals['provider']))
        record = super(ShippingAccount, self).create(vals)
        record._create_services()
        record._update_label_file_type()
        return record

    def write(self, vals):
        for record in self:
            if 'provider' in vals:
                vals.update(record._remove_redundant_field(vals['provider']))

        res = super(ShippingAccount, self).write(vals)
        for record in self:
            if 'provider' in vals:
                carriers = self.env['delivery.carrier'].sudo().search([('shipping_account_id.id', '=', record.id)])
                carriers.unlink()
                record._create_services()
            else:
                if any(field in vals for field in self._get_credential_fields()):
                    carriers = self.env['delivery.carrier'].sudo().with_context(active_test=False).search([('shipping_account_id.id', '=', record.id)])
                    credentials = {}
                    for field in vals:
                        credentials[field] = record[field]
                    carriers.sudo().write(credentials)

        if 'label_file_type' in vals:
            self._update_label_file_type()
        return res


