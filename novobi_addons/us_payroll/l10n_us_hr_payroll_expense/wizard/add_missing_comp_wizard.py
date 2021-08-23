from odoo import fields, models, api, _
from odoo.exceptions import UserError


class AddMissingCompWizard(models.TransientModel):
    _name = 'add.missing.comp.wizard'
    _description = 'Add missing compensations to scheduled period'

    def _get_pending_compensation_ids_domain(self):
        period_id = self.env.context.get('default_period_id', False)
        if period_id:
            period_id = self.env['pay.period'].browse(period_id)
            return period_id._get_missing_compensations_domain()
        else:
            return []

    period_id = fields.Many2one('pay.period', string='Pay Period')
    pending_compensation_ids = fields.Many2many('pending.compensation', string='Pending Compensations',
                                                domain=_get_pending_compensation_ids_domain)

    def button_add_missing_compensations(self):
        self.ensure_one()
        if not self.pending_compensation_ids:
            raise UserError(_('Please choose at least one compensation.'))

        for pending_comp in self.pending_compensation_ids:
            payslip_id = self.period_id.payslip_ids.filtered(lambda r: r.employee_id == pending_comp.employee_id)
            payslip_id.compensation_ids = [(0, 0, {
                'compensation_id': self.env.company.expense_compensation_id.id,
                'label': pending_comp.hr_expense_sheet_id.name,
                'amount': pending_comp.amount,
                'linked_pending_compensation_id': pending_comp.id
            })]
