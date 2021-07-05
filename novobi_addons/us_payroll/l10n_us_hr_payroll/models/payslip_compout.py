from odoo import api, fields, models


class PayslipCompOut(models.Model):
    _name = 'payslip.compout'
    _inherit = 'payslip.accumulated.amount'
    _description = 'Payslip Compensation History'
    _rec_name = 'tax_name'

    payslip_id = fields.Many2one('payroll.payslip', 'Payslip', ondelete='restrict')
    employee_id = fields.Many2one('hr.employee', 'Employee', related='payslip_id.employee_id', store=True)
    company_id = fields.Many2one('res.company', related='payslip_id.company_id', readonly=True, store=True)
    tax_name = fields.Char('Tax Name')
    tax_id = fields.Char('Tax ID')
    geocode = fields.Char('GeoCode')
    tax_type = fields.Char('Tax Type')
    school_dist = fields.Char('School District')
    comp_id = fields.Char('Comp ID')
    comp_type = fields.Char('Comp Type')
    amt = fields.Float('Amt Allowed', digits=(16, 2))

    pay_period_id = fields.Many2one('pay.period', related='payslip_id.pay_period_id', store=True)
    pay_date = fields.Date('Pay Date', related='pay_period_id.pay_date', store=True)

    def _prepare_domain(self):
        domain = super()._prepare_domain()

        payslip = self.payslip_id
        domain += [('company_id', '=', payslip.company_id.id),
                   ('tax_id', '=', self.tax_id),
                   ('geocode', '=', self.geocode),
                   ('tax_type', '=', self.tax_type),
                   ('school_dist', '=', self.school_dist),
                   ('comp_id', '=', self.comp_id),
                   ('comp_type', '=', self.comp_type)]

        return domain
