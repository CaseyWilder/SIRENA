# Copyright 2016 Trobz
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, models, fields


class OpePayrollReportWizard(models.TransientModel):
    _name = 'open.payroll.report.wizard'
    _description = 'Open payroll reports'

    report_type = fields.Selection(
        selection=[
            ('Compensation', 'Compensation'),
            ('Deduction', 'Deduction'),
            ('Taxes', 'Taxes'),
        ],
        string='Type',
        default='Compensation'
    )
    pay_period_id = fields.Many2one(
        'pay.period',
        'Pay period'
    )
    payroll_compensation_id = fields.Many2one(
        'payroll.compensation',
        'Compensation',
        help="Let it blank to see all compensations"
    )
    payroll_deduction_id = fields.Many2one(
        'payroll.deduction',
        'Deduction',
        help="Let it blank to see all deductions"
    )
    payroll_tax_id = fields.Many2one(
        'payroll.tax',
        'Tax',
        help="Let it blank to see all taxes"
    )

    def button_open(self):
        self.ensure_one()
        # Prepare general case
        origin_domain = []
        pay_period_id = self.pay_period_id
        if pay_period_id:
            origin_domain += [
                ('pay_period_id', '=', pay_period_id and pay_period_id.id)
            ]
        # Prepare specific cases
        report_type = self.report_type
        if report_type == 'Compensation':
            payroll_compensation_id = self.payroll_compensation_id or False
            action = self.env.ref('l10n_us_hr_payroll.action_payslip_compensation').read()[0]
            domain = origin_domain
            if payroll_compensation_id:
                domain += [('compensation_id', '=', payroll_compensation_id.id)]
            action['domain'] = domain
            return action

        elif report_type == 'Deduction':
            payroll_deduction_id = self.payroll_deduction_id or False
            action = self.env.ref('l10n_us_hr_payroll.action_payslip_deduction').read()[0]
            domain = origin_domain
            if payroll_deduction_id:
                domain += [('deduction_id', '=', payroll_deduction_id.id)]
            action['domain'] = domain
            return action

        elif report_type == 'Taxes':
            payroll_tax_id = self.payroll_tax_id or False
            action = self.env.ref('l10n_us_hr_payroll.action_payslip_tax').read()[0]
            domain = origin_domain
            if payroll_tax_id:
                domain += [('payroll_tax_id', '=', payroll_tax_id.id)]
            action['domain'] = domain
            return action

        return True
