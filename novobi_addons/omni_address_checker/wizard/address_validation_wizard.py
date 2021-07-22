from odoo import models, fields, api


class AddressValidationWizard(models.TransientModel):
    _name = 'address.validation.wizard'
    _description = 'Address Validation Wizard'

    # Old address
    address_id = fields.Many2one('res.partner')

    street = fields.Char(related='address_id.street')
    street2 = fields.Char(related='address_id.street2')
    city = fields.Char(related='address_id.city')
    zip = fields.Char(related='address_id.zip')
    state_id = fields.Many2one(related='address_id.state_id')
    country_id = fields.Many2one(related='address_id.country_id')
    address_classification = fields.Selection(related='address_id.address_classification')

    new_street = fields.Char('New Street')
    new_street2 = fields.Char('New Street2')
    new_city = fields.Char('New City')
    new_zip = fields.Char('New Zip')
    new_state_id = fields.Many2one('res.country.state', string='New State')
    new_country_id = fields.Many2one('res.country', string='New Country')
    new_address_classification = fields.Char('New Address Classification')

    @api.model
    def default_get(self, fields):
        res = super().default_get(fields)

        validated_address = self._context.get('validated_address', False)
        if validated_address:
            res.update(validated_address)

        return res

    def action_update_new_address(self):
        self.ensure_one()

        if not self.address_id:
            return

        self.address_id.write({
            'street': self.new_street,
            'street2': self.new_street2,
            'city': self.new_city,
            'zip': self.new_zip,
            'state_id': self.new_state_id.id,
            'country_id': self.new_country_id.id,
            'address_classification': self.new_address_classification if self.new_address_classification != 'UNKNOWN' else False
        })
