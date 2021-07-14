from datetime import timedelta

from odoo import api, models, fields, _
from odoo.exceptions import ValidationError


class HrDepartureWizard(models.TransientModel):
    _inherit = 'hr.departure.wizard'

    def _get_default_start_date(self):
        payslip_id = self.env['payroll.payslip'].search([('end_date', '!=', False)], order='end_date desc', limit=1)
        return payslip_id and payslip_id.end_date + timedelta(days=1) or False

    process_payroll = fields.Boolean('Process Termination Payroll', default=False)
    pay_date = fields.Date('Pay Date')
    start_date = fields.Date('Start Date', default=_get_default_start_date, help='Automatically get from end date of the last paycheck')
    end_date = fields.Date(string="End Date", default=fields.Date.today)
    include_deduction = fields.Boolean('Include Employee Deduction?', default=False)
    period_id = fields.Many2one('pay.period', 'Termination Payroll')

    @api.constrains('process_payroll', 'pay_date', 'start_date', 'end_date')
    def _check_payroll_date(self):
        for record in self.filtered('process_payroll'):
            if record.pay_date <= record.end_date:
                raise ValidationError(_('Pay Date must be greater than End Date.'))
            if record.end_date <= record.start_date:
                raise ValidationError(_('End Date must be greater than Start Date.'))

    def create_termination_period(self):
        payroll_data = self.employee_id.copy_payroll_data(incl_deduc=self.include_deduction)[0]
        return self.env['pay.period'].create({
            'name': 'Termination Payroll for {}'.format(self.employee_id.name),
            'pay_type': 'termination',
            'pay_frequency_id': payroll_data['pay_frequency_id'],
            'pay_date': self.pay_date,
            'start_date': self.start_date,
            'end_date': self.end_date,
            'payslip_ids': [(0, 0, payroll_data)]
        })

    def action_register_departure(self):
        """
        We move this feature to employee form, so need to archive the employee first to make it similar to the origin.
        Create the termination payroll for this employee if user ch
        :return:
        """
        if self.employee_id.active:
            self.employee_id.active = False
        if self.process_payroll:
            self.period_id = self.create_termination_period()

        super().action_register_departure()

    def action_register_departure_view_payroll(self):
        self.action_register_departure()
        return {
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'pay.period',
            'view_id': self.env.ref('l10n_us_hr_payroll.view_pay_period_form_termination').id,
            'target': 'current',
            'res_id': self.period_id.id,
            'context': {
                'form_view_initial_mode': 'edit'
            }
        }
