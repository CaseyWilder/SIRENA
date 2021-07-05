import logging

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

try:
    import holidays as hl
except ImportError as e:
    hl = None
    _logger.error(e)


class HrPublicHolidays(models.Model):
    _name = 'hr.public.holidays'
    _description = 'Public Holidays'
    _order = 'year'

    def _default_country(self):
        return self.env['res.country'].search([('code', '=', 'US')], limit=1)

    name = fields.Char('Name', compute='_compute_name', store=True)
    year = fields.Integer('Calendar Year', required=True, default=lambda self: fields.Date.context_today(self).year)
    year_str = fields.Char('Calendar Year (str)', compute='_compute_year_str')
    line_ids = fields.One2many('hr.public.holidays.line', 'year_id', string='Holiday Dates')
    country_id = fields.Many2one('res.country', string='Country', default=_default_country)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)
    state_id = fields.Many2one('res.country.state', string='State', domain=[('country_id.code', '=', 'US')])
    group_days_leave = fields.Float(string='Group Leaves', compute='_compute_group_days_leave')

    ####################################################################################################################
    # CONSTRAINTS
    ####################################################################################################################
    @api.constrains('year', 'state_id', 'company_id')
    def _check_year(self):
        """
        Each calendar (year, state, company) must be unique.
        """
        for record in self:
            domain = self._get_domain_unique_calendar(record.year, record.state_id.id, record.company_id.id)
            domain.append(('id', '!=', self.id))
            if self.search_count(domain):
                raise ValidationError(_(
                    'You can\'t create duplicate public holiday per year' +
                    '\nFound at  {} - {}'.format(record.year, record.state_id.name)
                ))

    ####################################################################################################################
    # ONCHANGE, COMPUTE/INVERSE
    ####################################################################################################################
    @api.depends('year')
    def _compute_year_str(self):
        for record in self:
            record.year_str = '{}'.format(record.year or '')

    @api.depends('year', 'state_id')
    def _compute_name(self):
        for record in self:
            if record.state_id:
                record.name = '{} - {}'.format(record.year, record.state_id.name)
            else:
                record.name = record.year

    def _compute_group_days_leave(self):
        grouped_res = self.env['hr.leave'].read_group(
            [('holiday_status_id.public_holiday_id', 'in', self.ids), ('holiday_type', '=', 'employee'), ('state', '=', 'validate')],
            ['holiday_status_id'],
            ['holiday_status_id'],
        )
        grouped_dict = dict((data['holiday_status_id'][0], data['holiday_status_id_count']) for data in grouped_res)
        for public_holiday in self:
            group_days_leave = 0.0
            for leave_type in self.env['hr.leave.type'].search([('public_holiday_id', '=', public_holiday.id)]):
                group_days_leave += grouped_dict.get(leave_type.id, 0)
            public_holiday.group_days_leave = group_days_leave

    ####################################################################################################################
    # ACTION
    ####################################################################################################################
    def action_generate_default_holidays(self, create_leave_type=True):
        for record in self.filtered(lambda r: r.country_id.code == 'US'):

            # Generate default holidays
            # E.g:  Holiday in on Sat (1/1/2022) -> this lib will generate an observed day on Fri (31/12/2021).
            # However, working calendar is from Mon to Thurs, therefore the observed day on Fir is useless.
            # So we do not generate the observed date by passing observed=False and let the user handle manually.
            default_holidays = hl.US(state=record.state_id.code, years=record.year, observed=False)
            holidays = self._get_specific_holidays(default_holidays)

            record.line_ids = [(0, 0, {
                'name': holiday_name,
                'date': dt,
            }) for dt, holiday_name in holidays.items()]

            # Create leave type
            if create_leave_type:
                record._create_leave_type()

    def button_generate_leave_requests(self):
        self.ensure_one()
        return self.line_ids.action_generate_leave_requests()

    def button_restore_default_holidays(self):
        self.ensure_one()
        self.line_ids = [(5, 0, 0)]
        self.action_generate_default_holidays(create_leave_type=False)

    def action_see_group_leaves(self):
        self.ensure_one()
        action = self.env.ref('l10n_us_hr_holidays.hr_leave_action_all').read()[0]
        action['domain'] = [('holiday_status_id.public_holiday_id', '=', self.id)]
        return action

    ####################################################################################################################
    # HELPER METHODS
    ####################################################################################################################
    def _get_domain_unique_calendar(self, year, state_id, company_id):
        return [
            ('year', '=', year),
            ('state_id', '=', state_id),
            ('company_id', '=', company_id),
        ]

    def _get_specific_holidays(self, raw_state_holidays):
        """
        This function allows you to change the holidays for adapting configuration at company level
        or whatever you want =))
        :param raw_state_holidays: {datetime: "holiday name"}
        :return: state_holidays: {datetime: "holiday name"}
        """
        state_holidays = raw_state_holidays
        # Example for Indiana & ICS
        # specific_holidays = self.env['ir.config_parameter'].sudo().get_param('us_leaves.specific_holidays')

        # if holiday_name == "Lincoln's Birthday":
        #     if state_id.code == 'IN':  # Indiana
        #         # Not sure why the Lincoln's birthday is the Day After Thanksgiving
        #         holiday_name = 'Day After Thanksgiving'

        return state_holidays

    def _create_leave_type(self):
        self.ensure_one()
        today = fields.Date.today()
        return self.env['hr.leave.type'].create({
            'name': 'Public Holidays - {} - {}'.format(self.state_id.name, self.year),
            'public_holiday_id': self.id,
            'request_unit': 'hour',
            'allocation_type': 'no',
            'exclude_public_holidays': False,
            'payroll_compensation_id': self.env.ref('l10n_us_hr_payroll.payroll_compensation_holiday').id,
            'company_id': self.company_id.id,
            'validity_start': today.replace(year=self.year, month=1, day=1),
            'validity_stop': today.replace(year=self.year, month=12, day=31)
        })

    @api.model
    @api.returns('hr.public.holidays.line')
    def get_holidays_list(self, year, employee_id=None):
        """
        Returns recordset of hr.public.holidays.line
        for the specified year and employee
        :param year: year as string
        :param employee_id: ID of the employee
        :return: recordset of hr.public.holidays.line
        """
        holidays_filter = [('year', '=', year)]
        employee = False
        if employee_id:
            employee = self.env['hr.employee'].browse(employee_id)
            if employee.address_id and employee.address_id.country_id:
                holidays_filter += ['|', ('country_id', '=', False),
                                    ('country_id', '=', employee.address_id.country_id.id)]
            else:
                holidays_filter.append(('country_id', '=', False))
        public_holidays = self.search(holidays_filter)
        if not public_holidays:
            return list()

        states_filter = [('year_id', 'in', public_holidays.ids)]
        if employee and employee.address_id and employee.address_id.state_id:
            states_filter += ['|', ('state_id', '=', False), ('state_id', '=', employee.address_id.state_id.id)]
        else:
            states_filter.append(('state_id', '=', False))

        return self.env['hr.public.holidays.line'].search(states_filter)

    @api.model
    def is_public_holiday(self, selected_date, employee_id=None):
        """
        Returns True if selected_date is a public holiday for the employee
        :param selected_date: datetime object
        :param employee_id: ID of the employee
        :return: bool
        """
        holidays_lines = self.get_holidays_list(selected_date.year, employee_id=employee_id)
        return bool(holidays_lines.filtered(lambda r: r.date == selected_date))

    def create_public_holidays(self, year, country_id, state_id, company_id):
        holiday = self.create({
            'year': year,
            'country_id': country_id,
            'state_id': state_id,
            'company_id': company_id
        })
        holiday.action_generate_default_holidays()
        return holiday

    def auto_create_public_holidays(self, year):
        """
        Helper method using for cron job to create calendar, generate and approve all leave requests.
        :param year:
        """
        country_id = self._default_country().id

        # We only create calendars (year, state, company) containing state and company which are set in Employees.
        query = """
            SELECT DISTINCT work_state_id, company_id
            FROM hr_employee
            WHERE work_state_id IS NOT NULL AND company_id IS NOT NULL
        """
        self.env.cr.execute(query)
        res = self.env.cr.fetchall()

        for work_state_id, company_id in res:
            # By pass if this calendar has been existed
            domain = self._get_domain_unique_calendar(year, work_state_id, company_id)
            if self.search_count(domain):
                continue

            # Create the calendar and its leave type.
            calendar = self.create_public_holidays(year, country_id, work_state_id, company_id)
            # # Generate and approve all leave requests from it.
            calendar.button_generate_leave_requests()

    ####################################################################################################################
    # CRON JOBS
    ####################################################################################################################
    @api.model
    def cron_generate_public_holiday(self):
        """
        Generate public holidays for all States in work state of employees (multi companies)
        """
        year = fields.Date.context_today(self).year

        # Check and create public holidays for current year
        self.auto_create_public_holidays(year)
        # Check and create public holidays for next year
        self.auto_create_public_holidays(year + 1)

        # Disable outdated_holiday_leaves flag after updating public holidays for all these employees.
        self.env['hr.employee']\
            .search([('company_id', '!=', False), ('work_state_id', '!=', False)])\
            .write({'outdated_holiday_leaves': False})
