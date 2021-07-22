from odoo import models, fields


class ResPartner(models.Model):
    _inherit = 'res.partner'

    is_address_validated = fields.Boolean(default=False)

    def get_validated_address(self, result):
        validated_address = result and result['validated_address']
        if not validated_address:
            return

        country = self.env['res.country'].search([('code', '=', validated_address.CountryCode)], limit=1)
        state = country.state_ids.filtered(lambda r: r.code == validated_address.StateOrProvinceCode)

        return {
            'new_street': validated_address.StreetLines[0],
            'new_street2': len(validated_address.StreetLines) > 1 and validated_address.StreetLines[1] or '',
            'new_city': validated_address.City,
            'new_zip': validated_address.PostalCode,
            'new_state_id': state.id,
            'new_country_id': country.id,
        }

    def write(self, vals):
        if not vals.get('is_address_validated', False):
            if any(field in vals for field in ['street', 'street2', 'city', 'zip', 'state_id', 'country_id']):
                vals['is_address_validated'] = False

        return super().write(vals)
