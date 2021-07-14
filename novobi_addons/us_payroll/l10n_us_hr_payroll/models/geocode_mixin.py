from odoo import api, fields, models
from ..utils.vertex import Vertex

# Fields to trigger get geocode
ADDRESS_LIST = ['city', 'county', 'state_id', 'zip']
WORK_ADDRESS_LIST = ['work_city', 'work_county', 'work_state_id', 'work_zip']

# Field name to get value and send to Vertex
GEO_VALUE_DICT = {'state_id': 'state_id',
                  'city': 'city',
                  'county': 'county',
                  'zip': 'zip',
                  'geocode_status': 'geocode_status',
                  'geocode': 'geocode',
                  'geocode_option_id': 'geocode_option_id'}
GEO_WORK_VALUE_DICT = {'state_id': 'work_state_id',
                       'city': 'work_city',
                       'county': 'work_county',
                       'zip': 'work_zip',
                       'geocode_status': 'work_geocode_status',
                       'geocode': 'work_geocode',
                       'geocode_option_id': 'work_geocode_option_id'}


class GeocodeMixin(models.AbstractModel):
    _name = "geocode.mixin"
    _description = "Geocode Mixin"

    def _get_geocode_option_domain(self):
        employee_id = self.env.context.get('employee_id', False)
        return [('employee_id', '=', employee_id)] if employee_id else []

    def _get_work_geocode_option_domain(self):
        work_employee_id = self.env.context.get('work_employee_id', False)
        return [('work_employee_id', '=', work_employee_id)] if work_employee_id else []

    geocode = fields.Char('GeoCode', groups="hr.group_hr_user")
    geocode_status = fields.Selection(
        [('draft', 'Draft'), ('empty', 'Not set'), ('value', 'Had value'), ('choice', 'Need to choose')],
        string='GeoCode Status', help='Store status of geocode', default='draft', groups="hr.group_hr_user")
    geocode_option_id = fields.Many2one('geocode.option', string='GeoCode Options', store=False,
                                        domain=_get_geocode_option_domain, groups="hr.group_hr_user")

    work_geocode = fields.Char('Work GeoCode', groups="hr.group_hr_user")
    work_geocode_status = fields.Selection(
        [('draft', 'Draft'), ('empty', 'Not set'), ('value', 'Had value'), ('choice', 'Need to choose')],
        string='Work GeoCode Status', help='Store status of geocode', default='draft', groups="hr.group_hr_user")
    work_geocode_option_id = fields.Many2one('geocode.option', string='Work GeoCode Options', store=False,
                                             domain=_get_work_geocode_option_domain, groups="hr.group_hr_user")

    def _update_geocode(self, values, option_field, address_list=None, value_dict=None):
        """
        IF choose the geocode in popup form => update geocode, geocode_status and county.
        ELSE (change address) => get geocode => update geocode, geocode_status based on the response.
        :param values: values in create/write function
        :param option_field: the relational field to link with geocode.option
        :param address_list: Geocode will be updated if users change these fields
        :param value_dict: field name to get value and send to Vertex
        """
        no_update = self.env.context.get('no_update', False)
        if no_update:
            return True
        geocode_updated = self.env.context.get('geocode_updated', False)

        address_list = address_list if address_list else ADDRESS_LIST
        value_dict = value_dict if value_dict else GEO_VALUE_DICT
        geocode_status = value_dict['geocode_status']
        geocode = value_dict['geocode']
        county = value_dict['county']

        for record in self:
            # Choose the geocode in popup form and click save:
            if geocode_updated:
                record._choose_geocode_option(values, geocode_status, geocode, county)

            # Change address (city, county, state_id, zip)
            else:
                if any(ele in values for ele in address_list):
                    result = Vertex().get_geocode(record, option_field, value_dict)
                    if len(result) == 0:
                        record.with_context(no_update=True).write({
                            geocode_status: 'empty',
                            geocode: False,
                        })
                    elif len(result) == 1:
                        record.with_context(no_update=True).write({
                            geocode_status: 'value',
                            geocode: result[0].geocode,
                            county: result[0].county
                        })
                    else:
                        record.with_context(no_update=True).write({
                            geocode_status: 'choice',
                            geocode: False,
                        })

    def _choose_geocode_option(self, values, geocode_status, geocode, county):
        geocode_option_id = values.get('work_geocode_option_id', False) if self.env.context.get('work_employee_id', False) \
            else values.get('geocode_option_id', False)
        if geocode_option_id:
            geocode_record = self.env['geocode.option'].browse(geocode_option_id)

            self.with_context(no_update=True).write({
                geocode_status: 'value',
                geocode: geocode_record.geocode,
                county: geocode_record.county
            })
        return True
