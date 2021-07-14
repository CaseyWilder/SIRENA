from odoo import fields, models, api, _


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    expense_compensation_id = fields.Many2one(related='company_id.expense_compensation_id', readonly=False)
