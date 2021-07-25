from odoo import models, fields

ADDRESS_CLASSIFICATION = [
    ('RESIDENTIAL', 'Residential Address'),
    ('BUSINESS', 'Business Address'),
    ('MIXED', 'Mixed Address')
]


class ResPartner(models.Model):
    _inherit = 'res.partner'

    address_classification = fields.Selection(ADDRESS_CLASSIFICATION)

    def get_validated_address(self, result):
        validated_address = result and result['validated_address']
        validated_address_classification = result and result['address_classification']
        if not validated_address or not validated_address_classification:
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
            'new_address_classification': validated_address_classification
        }

    def write(self, vals):
        if not vals.get('address_classification', False):
            if any(field in vals for field in ['street', 'street2', 'city', 'zip', 'state_id', 'country_id']):
                vals['address_classification'] = False

        return super().write(vals)
