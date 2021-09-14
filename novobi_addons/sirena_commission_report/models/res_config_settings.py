from odoo import models, fields


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    commission_journal_id = fields.Many2one(related='company_id.commission_journal_id', readonly=False)
    commission_amazon_journal_id = fields.Many2one(related='company_id.commission_amazon_journal_id', readonly=False)
