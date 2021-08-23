from odoo import models, fields, api, _
from odoo.exceptions import UserError


class PayDateLine(models.TransientModel):
    _name = 'pay.date.line'
    _description = 'All Pay Dates to create historical Periods'

    period_name = fields.Char('Period Name')
    pay_date = fields.Date('Pay Date')


class CreateHistoricalPeriodWizard(models.TransientModel):
    _name = 'create.historical.period.wizard'
    _description = 'Create Historical Periods with selected Employees'

    name = fields.Char('Name', default=lambda self: _('Import Historical Payroll'))
    employee_ids = fields.Many2many('hr.employee', string='Employees')
    pay_date_ids = fields.Many2many('pay.date.line', string='Pay Dates')
    pay_date = fields.Date('First Pay Date')
    instruction = fields.Html('Instruction', compute='_compute_instruction')

    @api.depends('pay_date')
    def _compute_instruction(self):
        for record in self:
            record.instruction = False
            if record.pay_date:
                quarter = (record.pay_date.month - 1) // 3 + 1

                quarter_msg = ""
                for i in range(1, quarter):
                    quarter_msg += "<li>One period contains YTD amounts on the last paystub in Q{}</li>".format(str(i))

                instruction = """
                <p>Your first pay check is in Quarter {}. You will need to create:</p>
                <ul>
                    {}
                    <li>A period for every paystub in this quarter</li>
                </ul>
                """.format(quarter, quarter_msg)
                record.instruction = instruction

    def _create_historical_period(self):
        """
        Create historical Period based on list of employees and pay dates.
        :return:
        """
        pay_date_ids, employee_ids = self.pay_date_ids, self.with_context(active_test=False).employee_ids
        if not pay_date_ids:
            raise UserError(_('Please insert Pay Dates to create Periods'))
        if not employee_ids:
            raise UserError(_('Please select Employees to add to Periods'))

        pay_frequency_id = self.with_context(active_test=False).employee_ids.mapped('pay_frequency_id')
        if not pay_frequency_id or len(pay_frequency_id) > 1:
            raise UserError(_('Please make sure that all chosen employees have same Pay Frequency'))

        pay_period_ids = self.env['pay.period']

        for record in pay_date_ids:
            period_name, pay_date = record.period_name, record.pay_date
            payroll_data = employee_ids.copy_payroll_data()
            values = {
                'name': period_name,
                'pay_date': pay_date,
                'pay_type': 'off',
                'is_history': True,
                'pay_frequency_id': pay_frequency_id.id,
            }
            if payroll_data:
                values['payslip_ids'] = [(0, 0, line) for line in payroll_data]
            pay_period_ids += self.env['pay.period'].create(values)

        return pay_period_ids

    def button_create_historical_period(self):
        self.ensure_one()
        pay_period_ids = self._create_historical_period()

        action = self.env.ref('l10n_us_hr_payroll.action_pay_period_form_off_cycle').read()[0]
        action['target'] = 'main'
        if pay_period_ids:
            domain = [('id', 'in', pay_period_ids.ids)]
            action['domain'] = domain

        # Set onboarding step to Done
        company = self.env.company
        company.set_onboarding_step_done('us_payroll_onboarding_historical_state')

        return action
