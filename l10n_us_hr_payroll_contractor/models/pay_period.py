from odoo.exceptions import UserError
from odoo import api, fields, models, _


class PayPeriod(models.Model):
    _inherit = 'pay.period'

    contain_contractor = fields.Boolean('Does this period contain all contractors', default=False, store=True)

    total_gross_pay_without_contractors = fields.Monetary('Total Gross Pay Excluding Contractors',
                                                          compute='_compute_total_amount_without_contractors',
                                                          store=True)

    @api.depends('payslip_ids', 'payslip_ids.employee_type')
    def _compute_contain_contractor(self):
        for period in self:
            employee_types = self.env['payroll.payslip'].search([('id', 'in', period.payslip_ids.ids)]).mapped(
                'employee_type')
            contain_all_contractors = all(list(map(lambda t: True if t == 'contractor' else False, employee_types)))
            if contain_all_contractors:
                period.contain_contractor = True
            else:
                period.contain_contractor = False

    @api.depends('state', 'payslip_ids')
    def _compute_dashboard_data(self):
        for record in self:
            payslip_ids = record.payslip_ids.filtered(lambda ps: ps.employee_type != 'contractor')
            if record.state == 'done' and payslip_ids:
                record.total_regular = sum(payslip_ids.mapped('regular'))
                record.total_overtime = sum(payslip_ids.mapped('overtime'))
                record.total_double = sum(payslip_ids.mapped('double_overtime'))
                record.total_holiday = sum(payslip_ids.mapped('holiday'))
                record.total_er_tax = sum(payslip_ids.mapped('total_er_tax'))
                record.total_er_deduction = sum(payslip_ids.mapped('total_er_deduction'))

    @api.depends('payslip_ids', 'payslip_ids.gross_pay')
    def _compute_total_amount_without_contractors(self):
        for period in self:
            if period.payslip_ids:
                period.total_gross_pay_without_contractors = sum(
                    period.payslip_ids.filtered(lambda ps: ps.employee_type != 'contractor').mapped('gross_pay'))

    def _check_time_tracking_rule(self):
        """
        Overwrite
        Do not check overtime rule of contractors
        """
        self.ensure_one()
        names = ''
        payslip_ids = self.payslip_ids.filtered(lambda r: r.employee_type != 'salary'
                                                          and r.employee_type != 'contractor'
                                                          and not r.time_tracking_id)
        if payslip_ids:
            for record in payslip_ids:
                names += '- ' + record.employee_id.name + '\n'
            raise UserError(_("""These employees need to be set Overtime Rule to get working hours:
                    {}Please check their profiles, then click 'Update Information' and try again.""".format(names)))
