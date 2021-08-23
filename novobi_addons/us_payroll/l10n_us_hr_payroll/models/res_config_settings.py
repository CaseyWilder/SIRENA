from odoo import fields, models, api, _


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    allow_payroll = fields.Boolean(related='company_id.allow_payroll', readonly=False)

    # Pay Frequency
    pay_frequency_id = fields.Many2one(related='company_id.pay_frequency_id', readonly=False)
    calculate_salary_by = fields.Selection(related='company_id.calculate_salary_by', readonly=False)

    # Overtime Rule
    time_tracking_id = fields.Many2one(related='company_id.time_tracking_id', readonly=False)
    checkin_method = fields.Selection(related='company_id.checkin_method', readonly=False)

    # Payroll Rate
    overtime_rate = fields.Float(related='company_id.overtime_rate', readonly=False)
    double_overtime_rate = fields.Float(related='company_id.double_overtime_rate', readonly=False)

    # Sync employee & contact
    sync_employee_contact = fields.Boolean(related='company_id.sync_employee_contact', readonly=False)

    # Payroll Account
    payroll_expense_account_id = fields.Many2one(related='company_id.payroll_expense_account_id', readonly=False)
    bank_account_id = fields.Many2one(related='company_id.bank_account_id', readonly=False)
    payroll_journal_id = fields.Many2one(related='company_id.payroll_journal_id', readonly=False)

    # FUTA
    override_futa_rate = fields.Boolean(related='company_id.override_futa_rate', readonly=False)
    futa_tax_rate = fields.Float(related='company_id.futa_tax_rate', readonly=False)

    # Onboarding
    us_payroll_dashboard_onboarding_state = fields.Selection(related='company_id.us_payroll_dashboard_onboarding_state')

    module_l10n_us_hr_timesheet = fields.Boolean('Timesheets for working hours')

    module_l10n_us_hr_payroll_contractor = fields.Boolean('Payroll Contractors')

    def button_action_sui_tax_view(self):
        return {
            'name': 'SUI Tax',
            'type': 'ir.actions.act_window',
            'view_mode': 'tree',
            'res_model': 'sui.tax',
            'target': 'current',
            'domain': [('company_id', '=', self.env.company.id)],
            'help': _('<p class="o_view_nocontent_smiling_face">Create your SUI Tax</p>')
        }

    def button_action_onboarding_dashboard(self):
        self.env.company.write({
            'us_payroll_dashboard_onboarding_state': 'not_done',
            'us_payroll_onboarding_pay_frequency_state': 'not_done',
            'us_payroll_onboarding_time_tracking_state': 'not_done',
            'us_payroll_onboarding_company_state': 'not_done',
            'us_payroll_onboarding_employee_state': 'not_done',
            'us_payroll_onboarding_historical_state': 'not_done',
        })

        # TODO: change into dashboard action instead
        return self.env.ref('l10n_us_hr_payroll.action_pay_period_form_frequency').read()[0]
