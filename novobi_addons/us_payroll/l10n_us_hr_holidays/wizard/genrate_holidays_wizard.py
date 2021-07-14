# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
from datetime import date

from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class GenerateHolidaysWizard(models.TransientModel):
    _name = 'generate.holidays.wizard'
    _description = 'Creates public holidays from existing ones'

    def _default_country(self):
        return self.env['res.country'].search([('code', '=', 'US')], limit=1)

    year_str = fields.Char('Calendar Year', default=date.today().year)
    year = fields.Integer(compute='_compute_year', store=True)
    country_id = fields.Many2one('res.country', string='Country', default=_default_country)
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    state_ids = fields.Many2many('res.country.state', 'wizard_state_rel', 'wizard_id', 'state_id',
                                 string='States', domain=[('country_id.code', '=', 'US')])

    @api.depends('year_str')
    def _compute_year(self):
        for record in self:
            try:
                record.year = int(record.year_str)
            except ValueError:
                raise UserError(_('Please correct the year by using format YYYY (e.g., 2019)'))

    def button_generate_public_holidays(self):
        self.ensure_one()
        public_holidays_env = self.env['hr.public.holidays']
        holiday_ids = self.env['hr.public.holidays']

        for state in self.state_ids:
            holiday_ids |= public_holidays_env.create_public_holidays(self.year, self.country_id.id, state.id, self.company_id.id)

        return {
            'type': 'ir.actions.act_window',
            'name': 'New public holidays',
            'view_mode': 'tree,form',
            'res_model': 'hr.public.holidays',
            'domain': [['id', 'in', holiday_ids.ids]]
        }
