from odoo import fields, models, api, _


class ResCompany(models.Model):
    _inherit = 'res.company'

    def _get_default_paystub_layout_id(self):
        return self.env.ref('l10n_us_payroll_check_printing.paystub_employee_address', raise_if_not_found=False) or self.env['ir.ui.view']

    include_company_contribution = fields.Boolean('Show Company Contribution in Paystub', default=False)
    include_historical_paystub = fields.Boolean('Show Historical Compensations/Deductions/Taxes in Paystub', default=True)
    paystub_layout_id = fields.Many2one('ir.ui.view', 'Paystub Layout', default=_get_default_paystub_layout_id)
