from odoo import fields, models, api, _


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    include_company_contribution = fields.Boolean(related='company_id.include_company_contribution', readonly=False)
    include_historical_paystub = fields.Boolean(related='company_id.include_historical_paystub', readonly=False)
    paystub_layout_id = fields.Many2one(related='company_id.paystub_layout_id', readonly=False)
