from odoo import models, fields, api, _
from odoo.addons.resource.models.resource import HOURS_PER_DAY
from odoo.tools import float_repr

from ..utils.utils import PAYROLL_CONFIDENTIAL_FIELDS

# Fields need to be synchronized between hr.employee and payroll_payslip.
EE_PAYSLIP_SYNC_FIELDS = [
    'company_id', 'employee_code', 'working_type', 'resource_calendar_id', 'address_id',
    'street', 'street2', 'city', 'county', 'zip', 'state_id', 'geocode',
    'work_street', 'work_street2', 'work_city', 'work_county', 'work_zip', 'work_state_id', 'work_geocode',
] + list(PAYROLL_CONFIDENTIAL_FIELDS)

STATE_TAX_INFO = ['state_pri_allow', 'state_sec_allow', 'state_add_wh', 'filing_status_id']
COUNTY_TAX_INFO = ['county_allow', 'county_add_wh']
CITY_TAX_INFO = ['city_allow', 'city_add_wh']


class PayslipMixin(models.AbstractModel):
    _name = 'payslip.mixin'
    _inherit = ['address.mixin', 'geocode.mixin']
    _description = 'Payroll Payslip Mixin'

    currency_id = fields.Many2one('res.currency', related='company_id.currency_id', readonly=True, store=True)
    employee_code = fields.Char(string='Employee ID', readonly=True, index=True, copy=False)
    working_type = fields.Selection([('full', 'Full-time'), ('part', 'Part-time')], string='Working Type',
                                    tracking=True, default='full')
    resource_calendar_id = fields.Many2one('resource.calendar', 'Working Schedule', tracking=True,
                                           default=lambda self: self.env.company.resource_calendar_id)

    # General Info
    pay_frequency_id = fields.Many2one('pay.frequency', 'Pay Frequency', tracking=True,
                                       domain="[('company_id', '=', company_id), ('state', '=', 'confirm')]")
    num_of_paychecks = fields.Integer('Number of Paychecks per year', compute='_compute_num_of_paychecks', store=True)
    time_tracking_id = fields.Many2one('time.tracking.rule', 'Overtime Rule', tracking=True)
    payment_method = fields.Selection([('check', 'Check'), ('deposit', 'Direct Deposit')],
                                      string='Payment Method', default='check', tracking=True)
    checkin_method = fields.Selection([('attendance', 'Attendances')], string='Check-in App',
                                      default=lambda self: self.env.company.checkin_method, tracking=True)

    # Employee Type & Salary
    employee_type = fields.Selection(
        [('salary_ovt', 'Salary/Eligible for Overtime'), ('salary', 'Salary/No Overtime'), ('hourly', 'Hourly')],
        string='Employee Type', tracking=True, default='salary')

    salary_amount = fields.Monetary('Salary', tracking=True)
    salary_period = fields.Selection([('52', 'Week'), ('12', 'Month'), ('1', 'Year')], string='Salary per period',
                                     tracking=True, default='52')
    salary_annual = fields.Monetary('Annual Salary', compute='_compute_payroll_salary', store=True, tracking=True)
    pay_rate = fields.Monetary('Pay Rate', compute='_compute_payroll_salary', store=True, tracking=True)
    # This field is to show Salary per Paycheck on employee form. On payslip, it is used as Salary Amount for current period.
    salary_per_paycheck = fields.Monetary('Salary per Paycheck', compute='_compute_payroll_salary', store=True,
                                          tracking=True)
    calculate_salary_by = fields.Selection([
        ('hour', 'Standard Working Hours'),
        ('paycheck', 'Fixed per Paycheck')
    ], string='Salary calculated by', default=lambda self: self.env.company.calculate_salary_by)
    salary_overridden = fields.Boolean('Sync salary with employee on updating information?', default=False,
                                       help='Technical field to decide if Salary is updated from Employee to Payslip or not.')

    address_id = fields.Many2one('res.partner', 'Work Address')
    vertex_id = fields.Char(string="Vertex ID", copy=False)

    # Tax Exemption
    exempt_social_security = fields.Boolean('Social Security', default=False, tracking=True)
    exempt_federal_tax = fields.Boolean('Federal Income Tax', default=False, tracking=True)
    exempt_medicare = fields.Boolean('Medicare', default=False, tracking=True)

    # Federal Info
    def _get_federal_filing_status_domain(self):
        return [('is_federal', '=', True)]

    fed_allow = fields.Integer('Federal Allowances', tracking=True)
    fed_add_wh = fields.Monetary('Federal Additional Withholding', tracking=True)
    fed_filing_status_id = fields.Many2one('filing.status', 'Federal Filing Status', tracking=True,
                                           domain=_get_federal_filing_status_domain)

    # State Info
    # Living State
    state_pri_allow = fields.Integer('Living State Primary Allowances', tracking=True)
    state_sec_allow = fields.Integer('Living State Secondary Allowances', tracking=True)
    state_add_wh = fields.Monetary('Living State Additional Withholding', tracking=True)
    filing_status_id = fields.Many2one('filing.status', 'Living Filing Status', tracking=True)
    alternate_calculation_id = fields.Many2one('alternate.calculation', 'Living Tax Rate Table', tracking=True)

    # Working State Info
    work_state_pri_allow = fields.Integer('Work State Primary Allowances', tracking=True)
    work_state_sec_allow = fields.Integer('Work State Secondary Allowances', tracking=True)
    work_state_add_wh = fields.Monetary('Work State Additional Withholding', tracking=True)
    work_filing_status_id = fields.Many2one('filing.status', 'Work Filing Status', tracking=True)
    work_alternate_calculation_id = fields.Many2one('alternate.calculation', 'Working Tax Rate Table', tracking=True)
    is_same_state = fields.Boolean('Work and Live in the same State?', compute='_compute_same_state', store=True)

    # W4 Label
    w4_primary_exempt = fields.Char(related='state_id.w4_primary_exempt')
    w4_second_exempt = fields.Char(related='state_id.w4_second_exempt')
    w4_primary_exempt_work = fields.Char(string='W4 Work Primary Exemption', related='work_state_id.w4_primary_exempt')
    w4_second_exempt_work = fields.Char(string='W4 Work Secondary Exemption', related='work_state_id.w4_second_exempt')

    # County Info
    county_allow = fields.Integer('Living County Allowance', tracking=True)
    county_add_wh = fields.Monetary('Living County Additional Withholding', tracking=True)
    work_county_allow = fields.Integer('Work County Allowance', tracking=True)
    work_county_add_wh = fields.Monetary('Work County Additional Withholding', tracking=True)
    is_same_county = fields.Boolean('Work and Live in the same County?', compute='_compute_same_county', store=True)

    # City
    city_allow = fields.Integer('Living City Allowance', tracking=True)
    city_add_wh = fields.Monetary('Living City Additional Withholding', tracking=True)
    work_city_allow = fields.Integer('Work City Allowance', tracking=True)
    work_city_add_wh = fields.Monetary('Work City Additional Withholding', tracking=True)
    is_same_city = fields.Boolean('Work and Live in the same City?', compute='_compute_same_city', store=True)

    # New W4 Form
    use_w4_2020 = fields.Boolean('Use 2020 Federal Form W-4?', default=False, tracking=True)
    multiple_jobs = fields.Boolean('Step 2: Multiple Jobs', tracking=True)
    claim_dependents = fields.Monetary('Step 3: Claim Dependents', tracking=True)
    other_income = fields.Monetary('Step 4a: Other Income', tracking=True)
    other_deduction = fields.Monetary('Step 4b: Other Deduction', tracking=True)

    ####################################################################################################################
    # CONSTRAINTS
    ####################################################################################################################
    # Monetary/Float fields must contain positive value
    _sql_constraints = [
        ('positive_payroll_salary_amount',      'CHECK (salary_amount >= 0)',       _('Salary Amount must be positive.')),
        ('positive_payroll_fed_add_wh',         'CHECK (fed_add_wh >= 0)',          _('Federal Additional Withholding must be positive.')),
        ('positive_payroll_state_add_wh',       'CHECK (state_add_wh >= 0)',        _('Living State Additional Withholding must be positive.')),
        ('positive_payroll_work_state_add_wh',  'CHECK (work_state_add_wh >= 0)',   _('Work State Additional Withholding must be positive.')),
        ('positive_payroll_county_add_wh',      'CHECK (county_add_wh >= 0)',       _('Living County Additional Withholding must be positive.')),
        ('positive_payroll_work_county_add_wh', 'CHECK (work_county_add_wh >= 0)',  _('Work County Additional Withholding must be positive.')),
        ('positive_payroll_city_add_wh',        'CHECK (city_add_wh >= 0)',         _('Living City Additional Withholding must be positive.')),
        ('positive_payroll_work_city_add_wh',   'CHECK (work_city_add_wh >= 0)',    _('Work City Additional Withholding must be positive.')),
        ('positive_payroll_claim_dependents',   'CHECK (claim_dependents >= 0)',    _('Claim Dependents (W4 - Step 3) must be positive.')),
        ('positive_payroll_other_income',       'CHECK (other_income >= 0)',        _('Other Income (W4 - Step 4a) must be positive.')),
        ('positive_payroll_other_deduction',    'CHECK (other_deduction >= 0)',     _('Other Deduction (W4 - Step 4b) must be positive.')),
    ]

    ####################################################################################################################
    # ONCHANGE, COMPUTE/INVERSE
    ####################################################################################################################
    @api.onchange('use_w4_2020')
    def _onchange_use_w4_2020(self):
        if not self.use_w4_2020:
            self.update({
                'fed_filing_status_id': False,
                'fed_add_wh': False,
                'fed_allow': False,
                'multiple_jobs': False,
                'claim_dependents': False,
                'other_income': False,
                'other_deduction': False
            })

    @api.depends('state_id', 'work_state_id')
    def _compute_same_state(self):
        self._compare_live_work('state_id', 'work_state_id', 'is_same_state', STATE_TAX_INFO)

    @api.depends('county', 'work_county')
    def _compute_same_county(self):
        self._compare_live_work('county', 'work_county', 'is_same_county', COUNTY_TAX_INFO)

    @api.depends('city', 'work_city')
    def _compute_same_city(self):
        self._compare_live_work('city', 'work_city', 'is_same_city', CITY_TAX_INFO)

    @api.depends('pay_frequency_id', 'pay_frequency_id.frequency')
    def _compute_num_of_paychecks(self):
        for record in self:
            record.num_of_paychecks = record.pay_frequency_id and int(record.pay_frequency_id.frequency) or False

    @api.depends('salary_amount', 'salary_period', 'employee_type', 'num_of_paychecks')
    def _compute_payroll_salary(self):
        """
        Calculate Annual Salary, Pay rate and Salary per Paycheck.
        This method should be in payslip.mixin (apply for both Payslip and Employee). When updating information
        in payslip, we only need to sync employee_type, salary_period and salary_amount.
        """
        for record in self:
            salary_per_paycheck = record.salary_per_paycheck
            salary_annual = 0
            if record.employee_type != 'hourly' and record.num_of_paychecks:
                salary_annual = record.salary_amount * int(record.salary_period or 1)
                if not record.salary_overridden:
                    salary_per_paycheck = salary_annual / record.num_of_paychecks

            record.salary_annual = salary_annual
            record.pay_rate = record._calculate_hourly_rate()
            record.salary_per_paycheck = salary_per_paycheck

    ####################################################################################################################
    # CRUD
    ####################################################################################################################
    @api.model
    def create(self, vals):
        res = super(PayslipMixin, self).create(vals)
        # Create Vertex ID from Employee ID (8 digits): e.g 13 -> 00000013
        res.vertex_id = str(res.id).zfill(8)
        return res

    ####################################################################################################################
    # HELPER METHODS
    ####################################################################################################################
    def _update_tax_information(self, field_list, work=False):
        vals = {}
        for field in field_list:
            vals[field] = self['work_' + field] if work else False
        return vals

    def _compare_live_work(self, live_add, work_add, is_same, list_field):
        for record in self:
            same_add = False
            if record[live_add] and record[work_add]:
                try:
                    same_add = record[work_add].lower().strip() == record[live_add].lower().strip()
                except AttributeError:
                    same_add = record[work_add].id == record[live_add].id

            record[is_same] = same_add

    def _calculate_standard_working_hours_per_week(self):
        return self.resource_calendar_id.hours_per_week or HOURS_PER_DAY * 5

    def _calculate_hourly_rate(self):
        """
        Calculate hourly rate for Salary/Eligible for Overtime employee.
        :return: hourly_rate
        """
        self.ensure_one()
        if self.employee_type != 'hourly':
            hours_per_week = self._calculate_standard_working_hours_per_week()
            return self.salary_annual / (hours_per_week * 52)
        return self.salary_amount

    def _format_currency_amount(self, amount):
        amount = float_repr(amount, precision_digits=self.currency_id.decimal_places)
        pre = post = u''
        if self.currency_id.position == 'before':
            pre = u'{symbol}\N{NO-BREAK SPACE}'.format(symbol=self.currency_id.symbol or '')
        else:
            post = u'\N{NO-BREAK SPACE}{symbol}'.format(symbol=self.currency_id.symbol or '')
        return u' {pre}{0}{post}'.format(amount, pre=pre, post=post)
