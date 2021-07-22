from odoo import models, fields, api


class PayPeriod(models.Model):
    _inherit = 'pay.period'

    total_regular = fields.Float('Total Regular Hours', digits=(16, 2), compute='_compute_dashboard_data', store=True)
    total_overtime = fields.Float('Total Overtime Hours', digits=(16, 2), compute='_compute_dashboard_data', store=True)
    total_double = fields.Float('Total Double Overtime Hours', digits=(16, 2), compute='_compute_dashboard_data', store=True)
    total_holiday = fields.Float('Total Paid Leaves Hours', digits=(16, 2), compute='_compute_dashboard_data', store=True)
    total_er_tax = fields.Monetary('Total Company Taxes', compute='_compute_dashboard_data', store=True)
    total_er_deduction = fields.Monetary('Total Company Contribution', compute='_compute_dashboard_data', store=True)

    @api.depends('state', 'payslip_ids')
    def _compute_dashboard_data(self):
        for record in self:
            payslip_ids = record.payslip_ids
            if record.state == 'done' and payslip_ids:
                record.total_regular = sum(payslip_ids.mapped('regular'))
                record.total_overtime = sum(payslip_ids.mapped('overtime'))
                record.total_double = sum(payslip_ids.mapped('double_overtime'))
                record.total_holiday = sum(payslip_ids.mapped('holiday'))
                record.total_er_tax = sum(payslip_ids.mapped('total_er_tax'))
                record.total_er_deduction = sum(payslip_ids.mapped('total_er_deduction'))
