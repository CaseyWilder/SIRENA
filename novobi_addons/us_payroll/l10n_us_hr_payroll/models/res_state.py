from odoo import api, fields, models
from ..utils.vertex import Vertex


class CountryState(models.Model):
    _inherit = 'res.country.state'

    vertex_id = fields.Char('Vertex ID')
    geocode = fields.Char('State GeoCode', compute='_compute_geocode', store=True)
    filing_status_ids = fields.Many2many('filing.status', string="Available Filing Statuses")
    alternate_calculation_ids = fields.Many2many('alternate.calculation', string="Alternate Calculation Tables")

    w4_primary_exempt = fields.Char('W4 Primary Exemption')
    w4_second_exempt = fields.Char('W4 Secondary Exemption')

    @api.depends('vertex_id')
    def _compute_geocode(self):
        for record in self:
            record.geocode = record.vertex_id + str('0'*7) if record.vertex_id else False

    @api.model
    def _update_filing_status(self):
        """
        Scheduler run monthly to update available filing statuses for all states
        """
        states = self.search([('vertex_id', '!=', 0)])
        pay_date = fields.Date.today()
        vertex = Vertex()

        # Get Filing status for Federal
        vertex.get_filing_status(self.env['res.country.state'], pay_date)

        for state in states:
            filing_status_ids = vertex.get_filing_status(state, pay_date)
            alter_cal_ids = vertex.get_alternate_calculation(state, pay_date)

            state.write({
                'filing_status_ids': [(6, 0, filing_status_ids)],
                'alternate_calculation_ids': [(6, 0, alter_cal_ids)]
            })
