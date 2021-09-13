from odoo import models, fields, api


class CommissionList(models.Model):
    _name = 'commission.report'
    _description = 'Commission Report'

    name = fields.Char(string='Name', compute='_compute_name')
    start_date = fields.Date('Start Date')
    end_date = fields.Date('End Date')
    is_amazon_report = fields.Boolean('Is Amazon Commission Report?')
    company_id = fields.Many2one('res.company', string='Company')
    commission_lines = fields.Many2many('sale.order.line', string='Commission Lines')

    @api.depends('start_date','end_date')
    def _compute_name(self):
        for rec in self:
            rec.name = '%s (%s - %s)' % ('Amazon' if rec.is_amazon_report else 'Sales', rec.start_date, rec.end_date)
