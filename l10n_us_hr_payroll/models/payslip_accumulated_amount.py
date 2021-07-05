from datetime import date
from odoo import api, fields, models, _
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT as DF


class PayslipAccumulatedAmount(models.AbstractModel):
    _name = "payslip.accumulated.amount"
    _description = "General model for calculating accumulated amount"

    # Payslip fields
    employee_id = fields.Many2one('hr.employee', 'Employee', related='payslip_id.employee_id', store=True, readonly=True)
    currency_id = fields.Many2one('res.currency', related='employee_id.currency_id', store=True, readonly=True)
    payslip_id = fields.Many2one('payroll.payslip', ondelete='cascade', required=1)
    state = fields.Selection(related='payslip_id.state', store=True)
    is_history = fields.Boolean(related='payslip_id.is_history', store=True)
    pay_period_id = fields.Many2one('pay.period', related='payslip_id.pay_period_id', store=True)
    pay_date = fields.Date('Pay Date', related='pay_period_id.pay_date', store=True)

    # Accumulated Amount
    mtd_amount = fields.Monetary('MTD', group_operator=None)
    qtd_amount = fields.Monetary('QTD', group_operator=None)
    ytd_amount = fields.Monetary('YTD', group_operator=None)

    def _prepare_domain(self):
        self.ensure_one()
        payslip = self.payslip_id
        year = self.pay_date.year

        return [
            ('employee_id', '=', payslip.employee_id.id),
            ('pay_date', '>=', date(year, 1, 1).strftime(DF)),
            ('pay_date', '<=', date(year, 12, 31).strftime(DF)),
            ('pay_period_id.state', '=', 'done'),
        ]

    def calculate_accumulated_amount(self, amount='amount'):
        for record in self:
            month = record.pay_date.month
            quarter = record.pay_period_id.quarter

            domain = record._prepare_domain()
            accumulated_amounts = self.search(domain)
            # Add the current confirmed record to calculate accumulated
            accumulated_amounts += record

            # Calculate month to date amount
            mtd_amount = sum(accumulated_amounts
                             .filtered(lambda pc: pc.pay_period_id and pc.pay_period_id.pay_date.month == month)
                             .mapped(amount))
            # Calculate quarter to date amount
            qtd_amount = sum(accumulated_amounts
                             .filtered(lambda pc: pc.pay_period_id and pc.pay_period_id.quarter == quarter)
                             .mapped(amount))
            # Calculate year to date amount
            ytd_amount = sum(accumulated_amounts.mapped(amount))

            record.write_accumulated_amount({
                'mtd_amount': mtd_amount,
                'qtd_amount': qtd_amount,
                'ytd_amount': ytd_amount
            })

        return True

    def write_accumulated_amount(self, vals):
        self.write(vals)
