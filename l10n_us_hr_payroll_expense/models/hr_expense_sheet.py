from odoo import api, fields, models, _


class HrExpenseSheet(models.Model):
    _inherit = 'hr.expense.sheet'

    pending_compensation_id = fields.Many2one('pending.compensation', string='Pending Compensation', copy=False)
    pay_with_payslip = fields.Boolean('Pay With Payslip', compute='_compute_pay_with_payslip')
    linked_payslip_id = fields.Many2one('payroll.payslip', related='pending_compensation_id.payslip_id')
    is_registered_payment = fields.Boolean(compute='_compute_is_registered_payment',
                                           help='Help to display Report In Next Payslip button')

    ####################################################################################################################
    # BUSINESS METHODS
    ####################################################################################################################

    def action_report_in_next_payslip(self):
        self.ensure_one()
        pending_compensation_id = self.env['pending.compensation'].create({
            'employee_id': self.employee_id.id,
            'amount': self.total_amount,
            'hr_expense_sheet_id': self.id,
            'date': self.accounting_date,
        })
        self.pending_compensation_id = pending_compensation_id

        return True

    def action_open_linked_payslip(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Payslip',
            'view_mode': 'form',
            'res_model': 'payroll.payslip',
            'res_id': self.linked_payslip_id.id
        }

    ####################################################################################################################
    # COMPUTE METHODS
    ####################################################################################################################

    @api.depends('amount_residual')
    def _compute_is_registered_payment(self):
        for record in self:
            record.is_registered_payment = record.total_amount != record.amount_residual and True or False

    @api.depends('pending_compensation_id')
    def _compute_pay_with_payslip(self):
        for record in self:
            record.pay_with_payslip = record.pending_compensation_id and True or False
