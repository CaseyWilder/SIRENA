from odoo import api, fields, models
from datetime import date
from dateutil.relativedelta import relativedelta


class DeductionEnrollmentPolicy(models.Model):
    _inherit = 'deduction.enrollment.policy'

    @api.depends('deduction_id', 'period', 'number', 'working_type')
    def _compute_eligible_employee_ids(self):
        super()._compute_eligible_employee_ids()
        for record in self:
            eligible_employee_ids = record.eligible_employee_ids
            eligible_employee_ids_without_contractors = eligible_employee_ids.filtered(
                lambda e: not e.employee_type == 'contractor')
            record.eligible_employee_ids = [(6, 0, eligible_employee_ids_without_contractors.ids)]
