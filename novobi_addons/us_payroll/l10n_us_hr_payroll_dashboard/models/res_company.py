from odoo import fields, models, api

DEFAULT_DEDUCTIONS_EXT_ID = [
    'l10n_us_hr_payroll.payroll_deduction_1',   # 401k Regular
    'l10n_us_hr_payroll.payroll_deduction_44',  # Health Insurance
    'l10n_us_hr_payroll.payroll_deduction_442', # Dental Insurance
    'l10n_us_hr_payroll.payroll_deduction_36',  # 125HSA Regular
    'l10n_us_hr_payroll.payroll_deduction_0',   # 125 Plan Regular
]


class ResCompany(models.Model):
    _inherit = 'res.company'

    def _get_default_deductions(self):
        deduction_ids = list()
        for external_id in DEFAULT_DEDUCTIONS_EXT_ID:
            deduction_id = self.env.ref(external_id, raise_if_not_found=False)
            if deduction_id:
                deduction_ids.append(deduction_id.id)

        return [(6, 0, deduction_ids)]

    @api.model
    def set_default_deductions(self):
        deduction_ids = self._get_default_deductions()
        self.search([]).write({'chart_deduction_ids': deduction_ids})

    # Dashboard
    chart_deduction_ids = fields.Many2many('payroll.deduction', string='Default Deductions in Dashboard', default=_get_default_deductions)
