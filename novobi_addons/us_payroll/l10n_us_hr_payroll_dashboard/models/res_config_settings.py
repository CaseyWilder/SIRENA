from odoo import fields, models, api, _


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # Dashboard
    chart_deduction_ids = fields.Many2many('payroll.deduction', string='Default Deductions in Dashboard',
                                           compute='_compute_chart_deduction_ids', inverse='_inverse_chart_deduction_ids')

    @api.depends('company_id.chart_deduction_ids')
    def _compute_chart_deduction_ids(self):
        for record in self:
            record.chart_deduction_ids = [(6, 0, record.company_id.chart_deduction_ids.ids)]

    def _inverse_chart_deduction_ids(self):
        for record in self:
            record.company_id.chart_deduction_ids = [(6, 0, record.chart_deduction_ids.ids)]
