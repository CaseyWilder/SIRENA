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

    number_payments = fields.Integer('Number of check payments', compute='_compute_number_payments')
    total_amount = fields.Float('Total Amount', compute='_compute_total_amount', store=True)

    @api.depends('start_date','end_date')
    def _compute_name(self):
        for rec in self:
            rec.name = '%s (%s - %s)' % ('Amazon' if rec.is_amazon_report else 'Sales', rec.start_date, rec.end_date)

    def _compute_number_payments(self):
        for record in self:
            record.number_payments = len(record.commission_lines.mapped('commission_payment'))

    @api.depends('commission_lines', 'commission_lines.commission_amount')
    def _compute_total_amount(self):
        for record in self:
            record.total_amount = sum(record.commission_lines.mapped('commission_amount'))

    def action_create_commission_payments(self):
        self.ensure_one()
        self.commission_lines.action_create_commission_payment()

    def action_view_commission_payments(self):
        self.ensure_one()
        return self.commission_lines.action_view_commission_payment()
