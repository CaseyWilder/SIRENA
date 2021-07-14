from odoo import models, fields, api
from odoo.addons.l10n_us_hr_payroll.models.payroll_payslip import SALARY_TYPE, SEQUENCE_PRIORITY


class PayrollPayslip(models.Model):
    _inherit = 'payroll.payslip'

    def _get_working_hours_template(self, field_get, calculate_by):
        """
        Override to clear overtime hours of contractor payslip and set regular hours = worked hours
        """
        self.ensure_one()
        if self.employee_type == 'contractor':
            total, _, _, _ = super(PayrollPayslip, self)._get_working_hours_template(field_get, calculate_by)
            return total, total, 0, 0
        else:
            return super(PayrollPayslip, self)._get_working_hours_template(field_get, calculate_by)

    def _update_compensation_list(self):
        """
        Override to add compensations for Contractor payslips: Add Salary line
        Execute when confirming payslip
        """
        super(PayrollPayslip, self)._update_compensation_list()

        for record in self:
            compensations = []
            hourly_rate = record.pay_rate
            employee_type = record.employee_type

            if record.is_history or employee_type != 'contractor' or (employee_type == 'contractor' and not hourly_rate):
                continue

            # Regular Pay for contractor
            com_id = record.env.ref(SALARY_TYPE['regular']).id
            regular_hours = record.regular
            label = 'Regular Pay'
            amount = hourly_rate * regular_hours
            comp = self.create_compensation(com_id, label, record.employee_id.id, amount, hourly_rate,
                                            regular_hours, SEQUENCE_PRIORITY['regular'])
            compensations.append(comp)

            record.write({'compensation_ids': [(0, 0, x) for x in compensations]})

    def _check_time_tracking_rule(self):
        """
        Override
        Allow to add contractor payslip with no overtime rule to pay period
        """
        self.ensure_one()
        if self.employee_type != 'contractor':
            super(PayrollPayslip, self)._check_time_tracking_rule()
