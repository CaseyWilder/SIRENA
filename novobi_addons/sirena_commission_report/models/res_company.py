from odoo import models, fields


class ResCompany(models.Model):
    _inherit = 'res.company'

    commission_journal_id = fields.Many2one('account.journal', 'Commission Report Journal')
    commission_amazon_journal_id = fields.Many2one('account.journal', 'Commission Report Journal (Amazon)')
