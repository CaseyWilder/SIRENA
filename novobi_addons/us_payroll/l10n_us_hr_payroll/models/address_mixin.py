from odoo import models, fields

# Fields need to be synchronized between hr.employee and res_partner.
EE_PARTNER_SYNC_FIELDS = ['name', 'street', 'street2', 'city', 'county', 'zip', 'phone', 'email', 'image_1920',
                          'state_id', 'country_id', 'company_id']


class AddressMixin(models.AbstractModel):
    _name = 'address.mixin'
    _description = 'Address Mixin'

    def _default_country(self):
        return self.env['res.country'].search([('code', '=', 'US')], limit=1)

    company_id = fields.Many2one('res.company', 'Company', index=True, default=lambda self: self.env.company)

    # Mailing Address
    street = fields.Char('Street', groups="hr.group_hr_user")
    street2 = fields.Char('Street2', groups="hr.group_hr_user")
    city = fields.Char('City', tracking=True, groups="hr.group_hr_user")
    county = fields.Char('County', tracking=True, groups="hr.group_hr_user")
    zip = fields.Char('ZipCode', change_default=True, tracking=True, groups="hr.group_hr_user")
    state_id = fields.Many2one('res.country.state', string='State', tracking=True,
                               domain="[('country_id', '=?', country_id)]", groups="hr.group_hr_user")
    country_id = fields.Many2one('res.country', string='Country', default=_default_country, groups="hr.group_hr_user")
    email = fields.Char('Email', groups="hr.group_hr_user")
    phone = fields.Char('Phone', groups="hr.group_hr_user")

    # Working Address
    work_street = fields.Char('Work Street', groups="hr.group_hr_user")
    work_street2 = fields.Char('Work Street2', groups="hr.group_hr_user")
    work_city = fields.Char('Work City', tracking=True, groups="hr.group_hr_user")
    work_county = fields.Char('Work County', tracking=True, groups="hr.group_hr_user")
    work_zip = fields.Char('Work ZipCode', change_default=True, tracking=True, groups="hr.group_hr_user")
    work_state_id = fields.Many2one('res.country.state', string='Work State', tracking=True,
                                    domain="[('country_id', '=?', work_country_id)]", groups="hr.group_hr_user")
    work_country_id = fields.Many2one('res.country', string='Work Country', default=_default_country, groups="hr.group_hr_user")
