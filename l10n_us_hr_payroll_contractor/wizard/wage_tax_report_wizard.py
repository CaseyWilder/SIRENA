from odoo import api, fields, models, _


class WageTaxReportWizard(models.TransientModel):
    _inherit = 'wage.tax.report.wizard'

    employee_ids = fields.Many2many(domain="[('company_id', '=', company_id), ('employee_type', '!=', 'contractor')]")
