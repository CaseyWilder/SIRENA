from odoo import models, fields, api


class GeocodeOptions(models.Model):
    _name = 'geocode.option'
    _description = 'Store options of Geocode'
    _order = 'county'

    geocode = fields.Char('GeoCode')
    city = fields.Char('City')
    county = fields.Char('County')
    state = fields.Char('State')
    zip_from = fields.Char('ZipCode From')
    zip_to = fields.Char('ZipCode To')

    # Add a many2one relationship here if you need to get geocode for that model
    employee_id = fields.Many2one('hr.employee', 'Employee')
    work_employee_id = fields.Many2one('hr.employee', 'Work Address of Employee')

    def name_get(self):
        result = []
        for record in self:
            name = "{} (ZipCode: {} - {})".format(record.county, record.zip_from, record.zip_to)
            result.append((record.id, name))
        return result
