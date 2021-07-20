from odoo import models, fields, _
from odoo.exceptions import UserError

from ..utils.fedex_request import FedexRequest


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    is_address_validated = fields.Boolean(related='partner_id.is_address_validated')

    def action_validate_address(self):
        fedex = self.env['shipping.account'].search([('provider', '=', 'fedex')], limit=1)
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
