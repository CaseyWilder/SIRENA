from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

import logging
_logger = logging.getLogger(__name__)


class SUITax(models.Model):
    _name = 'sui.tax'
    _order = 'state_id, start_date'
    _description = 'Employer State Unemployment Insurance Tax Rate'

    def _default_country(self):
        return self.env['res.country'].search([('code', '=', 'US')], limit=1)

    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    country_id = fields.Many2one('res.country', string='Country', default=_default_country)
    state_id = fields.Many2one('res.country.state', string='State', domain="[('country_id', '=?', country_id)]", required=True)
    start_date = fields.Date('Start Date', required=True, help='Period will apply this SUI Tax Rate')
    end_date = fields.Date('End Date', required=True, help='Period will apply this SUI Tax Rate')
    tax_rate = fields.Float('Tax Rate (%)', digits=(16, 3), required=True)
    state = fields.Selection([('outdated', 'Outdated'), ('applying', 'Applying'), ('incoming', 'Incoming')],
                             string='Status', compute='_compute_state')

    _sql_constraints = [
        ('positive_sui_tax_rate',   'CHECK(tax_rate >= 0)',             _('Tax Rate must be positive.')),
        ('end_greater_than_start',  'CHECK(end_date >= start_date)',    _('Start Date cannot be greater than End Date')),
    ]

    @api.constrains('company_id', 'state_id', 'start_date', 'end_date')
    def _check_unique_state_in_each_period(self):
        for record in self:
            query = """
                SELECT start_date, end_date
                FROM sui_tax
                WHERE company_id = {} AND state_id = {}
                ORDER BY start_date
            """.format(record.company_id.id, record.state_id.id)
            self.env.cr.execute(query)
            sui_tax_ids = self.env.cr.fetchall()
            same_states = len(sui_tax_ids) - 1
            if same_states > 0:
                for i in range(same_states):
                    next_start_date = sui_tax_ids[i + 1][0]
                    pre_end_date = sui_tax_ids[i][1]
                    if next_start_date and pre_end_date and next_start_date <= pre_end_date:  # Next start_date <= previous end_date => duplicated
                        raise ValidationError(_('SUI Tax for "{}" from {} to {} has been set, please remove the duplicates.'
                                                .format(record.state_id.display_name, sui_tax_ids[i][0], sui_tax_ids[i][1])))

    @api.depends('start_date', 'end_date')
    def _compute_state(self):
        for record in self:
            record.state = None
            start, end = record.start_date, record.end_date
            today = fields.Date.today()
            if start and end:
                record.state = 'incoming' if today < start else 'outdated' if today > end else 'applying'
