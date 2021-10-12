from odoo import api, models, fields, _
from odoo.exceptions import UserError

from ..utils.fedex_request import FedexRequest


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    address_classification = fields.Selection(related='partner_id.address_classification')

    def action_validate_address(self):
        fedex = self.sudo().env['shipping.account'].search([('provider', '=', 'fedex')], limit=1)
        if not fedex.fedex_account_number or not fedex.fedex_meter_number or not fedex.fedex_developer_key or not fedex.fedex_developer_password:
            raise UserError('Please add a FedEx shipping account or complete all FedEx credential fields if you haven\'t done so!')

        delivery_address = self.partner_id

        request = FedexRequest(self.delivery_carrier_id.get_debug_logger_xml(self),
                               request_type='validating',
                               prod_environment=fedex.prod_environment)
        request.web_authentication_detail(fedex.fedex_developer_key, fedex.fedex_developer_password)
        request.client_detail(fedex.fedex_account_number, fedex.fedex_meter_number)
        request.add_address_to_validation_request(delivery_address)

        result = request.process_validation(delivery_address)

        if result.get('errors_message', False):
            raise UserError(result['errors_message'])

        if result['matching_state'] != 'STANDARDIZED':
            raise UserError('Could not match your address against database reference data!')

        validated_address = delivery_address.get_validated_address(result)

        return {
            'name': _('Address Validation'),
            'view_mode': 'form',
            'res_model': 'address.validation.wizard',
            'type': 'ir.actions.act_window',
            'context': {
                'default_address_id': delivery_address.id,
                'validated_address': validated_address,
            },
            'target': 'new'
        }

    @api.onchange('fedex_service_type')
    def onchange_fedex_service_type(self):
        super().onchange_fedex_service_type()
        if self.fedex_service_type not in ['FEDEX_GROUND', 'GROUND_HOME_DELIVERY']:
            self.is_residential_address = self.address_classification == 'RESIDENTIAL'

    def open_create_label_form(self):
        # Set the default value for is_residential_address when opening the Create Label form:
        # + GROUND_HOME_DELIVERY -> True
        # + FEDEX_GROUND -> False
        # + Else, set based on address_classification of delivery address.
        self.ensure_one()
        if self.fedex_service_type in ['FEDEX_GROUND', 'GROUND_HOME_DELIVERY']:
            self.is_residential_address = self.fedex_service_type == 'GROUND_HOME_DELIVERY'
        else:
            self.is_residential_address = self.address_classification == 'RESIDENTIAL'
        return super().open_create_label_form()
