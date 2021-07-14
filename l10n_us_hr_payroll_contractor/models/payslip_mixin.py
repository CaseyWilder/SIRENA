from odoo import models, fields, api, _


class PayslipMixin(models.AbstractModel):
    _inherit = 'payslip.mixin'

    employee_type = fields.Selection(selection_add=[('contractor', 'Contractor')])

    def _calculate_hourly_rate(self):
        """
        Override to compute hourly rate of Contractor employee
        """
        self.ensure_one()
        if self.employee_type == 'contractor':
            return self.salary_amount
        else:
            return super(PayslipMixin, self)._calculate_hourly_rate()

    @api.depends('salary_amount', 'salary_period', 'employee_type', 'num_of_paychecks')
    def _compute_payroll_salary(self):
        """
        Override to set Annual Salary and Salary per Paycheck of contractor to 0
        """
        super(PayslipMixin, self)._compute_payroll_salary()
        for record in self.filtered(lambda r: r.employee_type == 'contractor'):
            record.salary_annual = 0
            record.salary_per_paycheck = 0
