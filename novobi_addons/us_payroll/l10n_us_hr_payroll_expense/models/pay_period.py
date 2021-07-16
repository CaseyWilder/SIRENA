from odoo import api, fields, models, _


class PayPeriod(models.Model):
    _inherit = 'pay.period'

    # ===== Helper fields =====
    missing_compensations = fields.Boolean('Missing Compensations?', compute='_compute_missing_compensations')
    hr_expense_sheet_ids = fields.Many2many('hr.expense.sheet', string='Linked Expense Reports',
                                            compute='_compute_expense_sheet_ids')

    ####################################################################################################################
    # HELPER METHODS
    ####################################################################################################################

    def _get_missing_compensations_domain(self):
        self.ensure_one()
        return [
            ('employee_id', 'in', self.payslip_ids.mapped('employee_id').ids),
            ('payslip_compensation_ids', '=', False)
        ]

    ####################################################################################################################
    # COMPUTE METHODS
    ####################################################################################################################
    @api.depends('payslip_ids')
    def _compute_missing_compensations(self):
        for record in self:
            comp_count = 0
            if record.state == 'draft':
                comp_count = self.env['pending.compensation'].search_count(record._get_missing_compensations_domain())
            record.missing_compensations = comp_count and True or False

    @api.depends('payslip_ids.compensation_ids')
    def _compute_expense_sheet_ids(self):
        for record in self:
            expense_sheet_ids = record.payslip_ids.compensation_ids.mapped('linked_pending_compensation_id.hr_expense_sheet_id.id')
            record.hr_expense_sheet_ids = [(6, 0, expense_sheet_ids)]

    ####################################################################################################################
    # BUSINESS METHODS
    ####################################################################################################################

    def button_add_missing_compensations(self):
        self.ensure_one()
        action = self.env.ref('l10n_us_hr_payroll_expense.action_add_missing_compensations_wizard').read()[0]
        action['context'] = {
            'default_period_id': self.id
        }
        return action

    def action_open_expense_reports(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Expense Reports',
            'view_mode': 'tree,form',
            'res_model': 'hr.expense.sheet',
            'domain': [('id', 'in', self.hr_expense_sheet_ids.ids)]
        }

    def button_done(self):
        res = super(PayPeriod, self).button_done()
        for record in self:
            record.hr_expense_sheet_ids.write({'state': 'done'})

        return res
