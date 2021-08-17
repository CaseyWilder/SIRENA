import logging

from odoo import fields, models, api, _

_logger = logging.getLogger(__name__)


class ResCompany(models.Model):
    _inherit = 'res.company'

    allow_payroll = fields.Boolean(default=True)

    # Pay Frequency
    pay_frequency_id = fields.Many2one('pay.frequency', 'Pay Frequency')
    calculate_salary_by = fields.Selection([
        ('hour', 'Standard Working Hours'),
        ('paycheck', 'Fixed per Paycheck')
    ], string='Salary calculated by', default='paycheck')

    # Overtime Rule
    time_tracking_id = fields.Many2one('time.tracking.rule', 'Overtime Rule')
    checkin_method = fields.Selection([('attendance', 'Attendances')], string='Check-in App', default='attendance')

    # Payroll Rate
    overtime_rate = fields.Float('Overtime Rate', default=1.5)
    double_overtime_rate = fields.Float('Double Overtime Rate', default=2)

    # Sync employee & contact
    sync_employee_contact = fields.Boolean('Sync Employee & Contact Information', default=False)

    # Payroll Account
    payroll_expense_account_id = fields.Many2one('account.account', 'Expense Account')
    bank_account_id = fields.Many2one('account.journal', 'Bank Account')
    payroll_journal_id = fields.Many2one('account.journal', 'Payroll Journal')

    # FUTA
    override_futa_rate = fields.Boolean('Override FUTA Rate', default=False)
    futa_tax_rate = fields.Float('Tax Rate (%)', digits=(16, 3))

    # ACH
    last_print_date = fields.Date('Last Print Date')
    last_print_file_id = fields.Char('Last File ID', default='A', required=True)

    # ONBOARDING
    us_payroll_dashboard_onboarding_state = fields.Selection([
        ('not_done', "Not done"), ('just_done', "Just done"), ('done', "Done"), ('closed', "Closed")],
        string="State of the US Payroll dashboard onboarding panel", default='not_done')
    # Steps
    us_payroll_onboarding_pay_frequency_state = fields.Selection([
        ('not_done', "Not done"), ('just_done', "Just done"), ('done', "Done")],
        string="State of the US Payroll onboarding pay frequency step", default='not_done')
    us_payroll_onboarding_time_tracking_state = fields.Selection([
        ('not_done', "Not done"), ('just_done', "Just done"), ('done', "Done")],
        string="State of the US Payroll onboarding time tracking step", default='not_done')
    us_payroll_onboarding_company_state = fields.Selection([
        ('not_done', "Not done"), ('just_done', "Just done"), ('done', "Done")],
        string="State of the US Payroll onboarding company step", default='not_done')
    us_payroll_onboarding_employee_state = fields.Selection([
        ('not_done', "Not done"), ('just_done', "Just done"), ('done', "Done")],
        string="State of the US Payroll onboarding employee step", default='not_done')
    us_payroll_onboarding_historical_state = fields.Selection([
        ('not_done', "Not done"), ('just_done', "Just done"), ('done', "Done")],
        string="State of the US Payroll onboarding historical data step", default='not_done')

    def get_and_update_us_payroll_dashboard_onboarding_state(self):
        """ This method is called on the controller rendering method and ensures that the animations
            are displayed only one time. """
        for record in self:
            # If users already add employees then the employee step should be done.
            if record.us_payroll_onboarding_employee_state == 'not_done':
                employees = self.env['hr.employee'].sudo().search([('company_id', '=', record.id)])
                if employees:
                    record.set_onboarding_step_done('us_payroll_onboarding_employee_state')

        return self.get_and_update_onbarding_state('us_payroll_dashboard_onboarding_state', [
            'us_payroll_onboarding_pay_frequency_state',
            'us_payroll_onboarding_time_tracking_state',
            'us_payroll_onboarding_company_state',
            'us_payroll_onboarding_employee_state',
            'us_payroll_onboarding_historical_state',
        ])

    @api.model
    def action_close_us_payroll_dashboard_onboarding(self):
        """ Mark the dashboard onboarding panel as closed. """
        self.env.company.us_payroll_dashboard_onboarding_state = 'closed'

    @api.model
    def setting_us_payroll_pay_frequency_action(self):
        """ Called by the 'Pay frequency' button of the Payroll setup bar."""
        view_id = self.env.ref('l10n_us_hr_payroll.view_pay_frequency_wizard_form').id

        return {
            'type': 'ir.actions.act_window',
            'name': _('Pay Frequency'),
            'view_mode': 'form',
            'res_model': 'pay.frequency',
            'target': 'new',
            'views': [[view_id, 'form']],
        }

    @api.model
    def setting_us_payroll_time_tracking_action(self):
        """ Called by the 'Overtime Rule' button of the Payroll setup bar."""
        view_id = self.env.ref('l10n_us_hr_payroll.view_time_tracking_rule_wizard_form').id

        return {
            'type': 'ir.actions.act_window',
            'name': _('Overtime Rule'),
            'view_mode': 'form',
            'res_model': 'time.tracking.rule',
            'target': 'new',
            'views': [[view_id, 'form']],
        }

    @api.model
    def setting_us_payroll_company_action(self):
        """ Called by the 'Company Data' button of the Payroll setup bar."""
        self.env.company.set_onboarding_step_done('us_payroll_onboarding_company_state')
        return self.env.ref('l10n_us_hr_payroll.action_us_payroll_configuration').read()[0]

    @api.model
    def setting_us_payroll_employee_action(self):
        """ Called by the 'Employees' button of the Payroll setup bar."""
        return self.env.ref('l10n_us_hr_payroll.hr_employee_action_payroll').read()[0]

    @api.model
    def setting_us_payroll_historical_action(self):
        """ Called by the 'Historical Data' button of the Payroll setup bar."""
        return self.env.ref('l10n_us_hr_payroll.action_create_historical_period_wizard_view').read()[0]

    @api.model
    def init_payroll_journal(self, create=False):
        """
        Handle 2 cases:
            1. On installing new l10n_us_hr_payroll (create=False):
                - Assign default Payroll Journal to current company
                - Create and assign Payroll Journal for other companies

            2. Create new company (create=True)
                - Create and assign Payroll Journal for that new company.
        """
        payroll_journal = self.sudo().env.ref('l10n_us_hr_payroll.account_journal_us_payroll')

        if not create:
            self.env.company.payroll_journal_id = payroll_journal.id

        # This is to apply for installing new l10n_us_hr_payroll (no company is passed to self)
        if not self:
            self = self.search([('payroll_journal_id', '=', False)])

        for record in self:
            # We should auto create Chart of Accounts for this company first, then assign Payroll Journal later.
            if not record.chart_template_id:
                record.install_chart_of_account()
            record.install_payroll_journal(payroll_journal)

    def install_chart_of_account(self):
        self.ensure_one()
        self = self.sudo()
        chart_template_id = self.env.ref('l10n_generic_coa.configurable_chart_template')
        chart_template_id._load(15.0, 15.0, self)
        _logger.info('Chart of Accounts are installed for Company: {} ({})'.format(self.name, self.id))

    def install_payroll_journal(self, payroll_journal):
        self.ensure_one()
        journal = payroll_journal.copy(default={'company_id': self.id})
        journal.name = payroll_journal.name

        self.env['ir.model.data'].create({
            'module': 'l10n_us_hr_payroll',
            'name': 'account_journal_us_payroll' + str(self.id),
            'model': 'account.journal',
            'noupdate': True,
            'res_id': journal.id,
        })
        self.payroll_journal_id = journal

    @api.model
    def create(self, values):
        res = super().create(values)
        res.init_payroll_journal(create=True)
        return res
