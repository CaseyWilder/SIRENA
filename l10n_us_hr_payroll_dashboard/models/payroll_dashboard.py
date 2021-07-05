import json
from math import ceil

from odoo import models, fields, api, _
from datetime import timedelta

from ..utils.dashboard import BY_PERIOD, BY_MONTH, BY_QUARTER, BY_YEAR, BY_LAST_MONTH, BY_LAST_QUARTER, BY_LAST_YEAR, \
    GROUP_BY_PERIOD, GROUP_BY_WEEK, GRAPH_COLOR,\
    get_json_data_for_selection, get_json_render, format_currency, format_value, group_graph_data

from odoo.addons.l10n_custom_dashboard.utils.graph_setting import get_chartjs_setting, get_barchart_format, get_piechart_format, get_chart_json

pieColor = [
    GRAPH_COLOR['blue'], GRAPH_COLOR['orange'], GRAPH_COLOR['green'],
    GRAPH_COLOR['purple'], GRAPH_COLOR['silver'], GRAPH_COLOR['lightgreen']
]

MAX_LINES = 4

RAINBOW_MAN = json.dumps({
    # Custom setting of rainbow_man here
    'type': 'rainbow_man',
    'fadeout': 'no',
    'message': _('Well-done! Current scheduled payroll has been done.'),
    'payroll_custom': {
        'delay': False,
        'delayTime': 0,
        'close_on_click': False
    },
})


class PayrollDashboard(models.Model):
    _name = 'payroll.dashboard'
    _description = 'Payroll Dashboard'
    _order = 'sequence'

    sequence = fields.Integer('Sequence', default=10)
    color = fields.Integer('Color Index')
    type = fields.Selection([
        ('todo', 'Things To Do'),
        ('employees', 'Employees'),
        ('tbd', 'Deductions'),
        ('hours', 'Hours per Pay Rate'),
        ('gross', 'Gross Pay Breakdown'),
        ('cost', 'Payroll Cost')
    ], string='Type', required=True, readonly=True)

    name = fields.Char('Name', compute='_compute_name')

    kanban_dashboard_graph = fields.Text(compute='_compute_kanban_dashboard_graph')

    # Options to filter data in different period
    # Group by:
    #   1. Last Scheduled Period
    #   2. This Month/Quarter/Year
    #   3. Last Month/Quarter/Year
    time_filter = [
        {'name': 'Last Scheduled Period',   'delta': 0,     'type': BY_PERIOD,          'separate': True},
        {'name': 'This Month',              'delta': 0,     'type': BY_MONTH,           'separate': False},
        {'name': 'This Quarter',            'delta': 0,     'type': BY_QUARTER,         'separate': False},
        {'name': 'This Year',               'delta': 0,     'type': BY_YEAR,            'separate': True},
        {'name': 'Last Month',              'delta': -1,    'type': BY_LAST_MONTH,      'separate': False},
        {'name': 'Last Quarter',            'delta': -1,    'type': BY_LAST_QUARTER,    'separate': False},
        {'name': 'Last Year',               'delta': -1,    'type': BY_LAST_YEAR,       'separate': False},
    ]
    default_time_filter = BY_PERIOD

    # Things To Do
    current_period_id = fields.Many2one('pay.period', string='Current Period', compute='_compute_current_period')
    period_calendar = fields.Text(compute='_compute_current_period')
    period_rainbow_man = fields.Text(compute='_compute_current_period')
    number_pending_leaves = fields.Integer('Number of Pending Leaves Requests', compute='_compute_number_pending_leaves')
    number_pending_paid = fields.Integer('Number of Termed Employees but not yet paid', compute='_compute_number_pending_paid')
    number_term_payroll = fields.Integer('Number of Termination Payroll in progress', compute='_compute_number_term_payroll')
    number_deduction_enrollment = fields.Integer('Number of Deduction Enrollment', compute='_compute_number_deduction_enrollment')

    # Employees
    number_total_emp = fields.Integer('Number of Total Employees', compute='_compute_number_total_emp')
    number_fulltime_emp = fields.Integer('Number of Full-time Employees', compute='_compute_number_fulltime_emp')
    number_parttime_emp = fields.Integer('Number of Part-time Employees', compute='_compute_number_parttime_emp')
    number_absent_emp = fields.Integer('Number of Absent Employees today', compute='_compute_number_absent_emp')
    holidays = fields.Html(string='Upcoming Holidays', sanitize=False, compute='_compute_holidays')
    birthday = fields.Html(string='Upcoming Birthday', sanitize=False, compute='_compute_birthday')

    @api.depends('type')
    def _compute_name(self):
        for record in self:
            record.name = dict(record._fields['type'].selection).get(record.type)

    def _compute_kanban_dashboard_graph(self):
        for record in self:
            dashboard_type = record.type
            type_data = 'doughnut' if dashboard_type == 'gross' else 'bar'
            extend_mode, graph_data = self.get_general_kanban_section_data()
            selection = []
            get_json_data_for_selection(record, selection)
            function_retrieve = 'retrieve_payroll_dashboard'
            extra_param = dashboard_type
            record.kanban_dashboard_graph = json.dumps(get_json_render(type_data, False, graph_data, dashboard_type, selection, function_retrieve, extra_param))

    def get_general_kanban_section_data(self):
        return False, [{
            'values': [],
            'title': '',
            'key': '',
            'color': ''
        }]

    def _get_current_period(self):
        frequency_id = self.env.company.pay_frequency_id
        if frequency_id:
            return self.env['pay.period'].search([('pay_frequency_id', '=', frequency_id.id), ('state', '!=', 'done')],
                                                 order='pay_date desc', limit=1)
        return self.env['pay.period']

    ####################################################################################################################
    # THINGS TO DO
    ####################################################################################################################
    def _compute_current_period(self):
        # Get the last in-progress period
        frequency_id = self.env.company.pay_frequency_id
        period_id = self.env['pay.period']
        if frequency_id:
            period_id = period_id.search([
                ('pay_type', '=', 'frequency'),
                ('pay_frequency_id', '=', frequency_id.id),
                ('state', '!=', 'done')
            ], order='pay_date desc', limit=1)

        for record in self:
            period_rainbow_man = current_period_id = period_calendar = False
            if record.type == 'todo':
                period_rainbow_man = RAINBOW_MAN
                current_period_id = period_id

                if period_id:
                    deadline = frequency_id and frequency_id.deadline or 0
                    start_date = period_id.start_date
                    end_date = period_id.end_date
                    pay_date = period_id.pay_date
                    deadline = pay_date - timedelta(days=min(deadline, (pay_date - end_date).days))

                    period_calendar = json.dumps({
                        # Format '%Y-%m-%d' => JS => UTC(0, 0, 0, 0)
                        # Format '%m/%d/%Y' => JS => User's timezone(0, 0, 0, 0)
                        'start_date': start_date.strftime('%m/%d/%Y'),
                        'end_date': end_date.strftime('%m/%d/%Y'),
                        'pay_date': pay_date.strftime('%m/%d/%Y'),
                        'deadline': deadline.strftime('%m/%d/%Y')
                    })

            record.period_rainbow_man = period_rainbow_man
            record.current_period_id = current_period_id
            record.period_calendar = period_calendar

    def button_see_current_period(self):
        """
        Button to see the current period (Scheduled Payroll).
        :return: action
        """
        self.ensure_one()
        view_id = self.env.ref('l10n_us_hr_payroll.view_pay_period_form_frequency')
        return {
            'name': 'Scheduled Payroll',
            'type': 'ir.actions.act_window',

            'view_mode': 'form',
            'res_model': 'pay.period',
            'view_id': view_id.id,
            'target': 'current',
            'res_id': self.current_period_id.id,
        }

    # Pending Leave Requests
    def _get_domain_pending_leaves(self):
        return [
            ('state', 'in', ['draft', 'confirm', 'validate1']),
            ('holiday_status_id.company_id', '=', self.env.company.id)
        ]

    def _compute_number_pending_leaves(self):
        """
        Get number of pending leaves (To Submit (draft) / To Approve (confirm)).
        """
        domain = self._get_domain_pending_leaves()
        number = self.env['hr.leave'].search_count(domain)
        for record in self:
            record.number_pending_leaves = number

    def button_see_leave_requests(self):
        """
        Button to see pending leaves (To Submit (draft) / To Approve (confirm)).
        :return: action
        """
        self.ensure_one()
        domain = self._get_domain_pending_leaves()
        return {
            'name': 'Pending Leave Requests',
            'type': 'ir.actions.act_window',
            'view_mode': 'tree,form',
            'res_model': 'hr.leave',
            'target': 'current',
            'domain': domain,
        }

    # Pending Payments for Termination
    def _get_domain_pending_paid(self):
        termination_payrolls = self.env['payroll.payslip'].search([
            ('pay_type', '=', 'termination'),
            ('state', '!=', 'done')
        ])
        return [('id', 'in', termination_payrolls.mapped('employee_id').ids)]

    def _compute_number_pending_paid(self):
        """
        Get number of pending payments (termed employees but not yet paid).
        """
        domain = self._get_domain_pending_paid()
        number = self.env['hr.employee'].with_context(active_test=False).search_count(domain)
        for record in self:
            record.number_pending_paid = number

    def button_see_pending_paid_employees(self):
        self.ensure_one()
        domain = self._get_domain_pending_paid()
        return self._get_employee_action_view(name=_('Pending Paid Employees'), domain=domain)

    def _get_domain_term_payroll(self):
        return [
            ('pay_type', '=', 'termination'),
            ('state', '!=', 'done'),
            ('company_id', '=', self.env.company.id)
        ]

    def _compute_number_term_payroll(self):
        domain = self._get_domain_term_payroll()
        number = self.env['pay.period'].search_count(domain)
        for record in self:
            record.number_term_payroll = number

    def button_see_termination_payroll(self):
        """
        Button to see termination payrolls.
        :return: action
        """
        self.ensure_one()
        domain = self._get_domain_term_payroll()
        action = self.env.ref('l10n_us_hr_payroll.action_pay_period_form_termination').read()[0]
        action['domain'] = domain
        return action

    # Pending Deduction Enrollment
    def _get_deduction_enrollment_ids(self):
        # 'eligible_employee_ids' is not stored so cannot use domain to search.
        return self.env['deduction.enrollment.policy']\
            .search([])\
            .filtered('eligible_employee_ids').ids

    def _compute_number_deduction_enrollment(self):
        number = len(self._get_deduction_enrollment_ids())
        for record in self:
            record.number_deduction_enrollment = number

    def button_see_deduction_enrollment(self):
        self.ensure_one()
        policy_ids = self._get_deduction_enrollment_ids()
        return {
            'name': 'Pending Deduction Enrollment',
            'type': 'ir.actions.act_window',

            'view_mode': 'tree,form',
            'res_model': 'deduction.enrollment.policy',
            'domain': [('id', 'in', policy_ids)],
            'target': 'current',
        }

    ####################################################################################################################
    # EMPLOYEES
    ####################################################################################################################
    def _get_employee_action_view(self, name='Employees', domain=[], target='current'):
        return {
            'name': name,
            'type': 'ir.actions.act_window',
            'view_mode': 'kanban,tree,form',
            'res_model': 'hr.employee',
            'context': {
                'active_test': False,
                'form_view_ref': 'l10n_us_hr_payroll.hr_employee_view_form'
            },
            'domain': domain,
            'target': target,
        }

    # Total employees
    def _get_domain_total_employees(self):
        return [
            ('departure_date', '=', False),
            ('company_id', '=', self.env.company.id)
        ]

    def _compute_number_total_emp(self):
        """
        Get number of all employees.
        """
        domain = self._get_domain_total_employees()
        number = self.env['hr.employee'].with_context(active_test=False).search_count(domain)
        for record in self:
            record.number_total_emp = number

    def button_see_all_employees(self):
        """
        Button to see all employees.
        :return: action
        """
        self.ensure_one()
        domain = self._get_domain_total_employees()
        return self._get_employee_action_view(name=_('All Employees'), domain=domain)

    # Absent employees
    def _get_domain_absent_employees(self):
        today = fields.Date.today()
        return [
            ('state', '=', 'validate'),
            ('request_date_from', '<=', today),
            ('request_date_to', '>=', today),
            ('holiday_status_id.company_id', '=', self.env.company.id)
        ]

    def _compute_number_absent_emp(self):
        """
        Get number of absent employees today.
        """
        domain = self._get_domain_absent_employees()
        employee_ids = self.env['hr.leave'].search(domain).mapped('employee_id').filtered(lambda r: not r.departure_date)
        number = len(employee_ids)
        for record in self:
            record.number_absent_emp = number

    def button_see_absent_employees(self):
        """
        Button to see absent employees today.
        :return: action
        """
        self.ensure_one()
        domain = self._get_domain_absent_employees()
        employee_ids = self.env['hr.leave'].search(domain).mapped('employee_id')
        domain = [('id', 'in', employee_ids.ids), ('departure_date', '=', False)]
        return self._get_employee_action_view(name=_('Absent Employees today'), domain=domain)

    # Full-time employee
    def _get_domain_fulltime_employees(self):
        return [
            ('working_type', '=', 'full'),
            ('departure_date', '=', False),
            ('company_id', '=', self.env.company.id)
        ]

    def _compute_number_fulltime_emp(self):
        """
        Get number of full-time employees.
        """
        domain = self._get_domain_fulltime_employees()
        number = self.env['hr.employee'].with_context(active_test=False).search_count(domain)
        for record in self:
            record.number_fulltime_emp = number

    def button_see_fulltime_employees(self):
        """
        Button to see full-time employees.
        :return: action
        """
        self.ensure_one()
        domain = self._get_domain_fulltime_employees()
        return self._get_employee_action_view(name=_('Full-time Employees'), domain=domain)

    # Part-time employees
    def _get_domain_parttime_employees(self):
        return [
            ('working_type', '=', 'part'),
            ('departure_date', '=', False),
            ('company_id', '=', self.env.company.id)
        ]

    def _compute_number_parttime_emp(self):
        """
        Get number of part-time employees.
        """
        domain = self._get_domain_parttime_employees()
        number = self.env['hr.employee'].with_context(active_test=False).search_count(domain)
        for record in self:
            record.number_parttime_emp = number

    def button_see_parttime_employees(self):
        """
        Button to see part-time employees.
        :return: action
        """
        self.ensure_one()
        domain = self._get_domain_parttime_employees()
        return self._get_employee_action_view(name=_('Part-time Employees'), domain=domain)

    # Add new employee.
    def button_add_new_employee(self):
        """
        Button to add new employee.
        :return: action
        """
        self.ensure_one()
        action = self._get_employee_action_view(name=_('New Employees'))
        action['view_mode'] = 'form'
        action['res_id'] = False
        del action['domain']

        return action

    def _get_upcoming_date(self, query_result, field, sort=False):

        html_template = """
            <div class="upcoming-date border-item">
                <div class="date-container">
                    <div class="date">
                        <div class="month">{month}</div>
                        <div class="day">{day}</div>
                    </div>
                </div>
                <div class="name bold-text">{name}</div>
            </div>
        """

        if query_result:
            if sort:
                months = set(map(lambda x: x[1].month, query_result))
                query_result.sort(key=lambda x: (x[1].month % 12 if {1, 12} <= months else x[1].month) * 31 + x[1].day)
            html = '<div class="list-box">'
            for data in query_result:
                html += html_template.format(month=data[1].strftime('%b'), day=data[1].strftime('%d'), name=data[0])
            html += '</div>'
        else:
            html = '<div class="mt-3">There is no upcoming {}.</div>'.format(field)

        return html

    # Upcoming Holidays
    def _compute_holidays(self):
        state_id = self.env.company.state_id
        if not state_id:
            html = '<div class="mt-3 text-warning">You have not set State Address for your company</div>'
        else:
            query = """
                SELECT name, date
                FROM hr_public_holidays_line
                WHERE state_id = {} AND date BETWEEN CURRENT_DATE AND CURRENT_DATE + INTERVAL '1 mons'
                ORDER BY date;
            """.format(state_id.id)
            self.env.cr.execute(query)
            query_result = self.env.cr.fetchall()
            html = self._get_upcoming_date(query_result, field='holiday')

        for record in self:
            record.holidays = html

    # Upcoming Birthday
    def _compute_birthday(self):
        # Query structure:
        #   SELECT name, date
        #   FROM
        #       (SELECT *, EXTRACT(MONS from age(date)) AS mons, EXTRACT(DAYS from age(date)) AS days
        #       FROM <table>) tb
        #   WHERE <conditions> AND (mons = 11 OR mons = 0 AND days <= 0);

        # Result structure:
        #   age(date) return "a years b mons c days d hours e mins f secs"
        #   Example, if today = 15/10/2019
        #       date = 14/10/2018 => age(date) = 1 years 0 mons 1 days ...
        #       date = 16/10/2018 => age(date) = 0 years 11 mons 30 days ...
        #       date = 18/10/2019 => age(date) = 0 years 0 mons -3 days ...
        #       date = 26/12/2019 => age(date) = 0 years -2 mons -11 days ...
        #   => For upcoming date in a month: mons = 11 or mons = 0 and days <= 0
        query = """
            SELECT name, birthday
            FROM
                (SELECT *, EXTRACT(MONS from age(birthday)) AS mons, EXTRACT(DAYS from age(birthday)) AS days
                FROM hr_employee) bd
            WHERE company_id = {} AND departure_date IS NULL AND (mons = 11 OR mons = 0 AND days <= 0);
        """.format(self.env.company.id)
        self.env.cr.execute(query)
        query_result = self.env.cr.fetchall()
        html = self._get_upcoming_date(query_result, field='birthday', sort=True)

        for record in self:
            record.birthday = html

    ####################################################################################################################
    # DEDUCTIONS
    ####################################################################################################################
    def button_see_deductions(self):
        """
        Button to open Deduction report.
        :return: action
        """
        self.ensure_one()
        action = self.env.ref('l10n_us_hr_payroll.action_payslip_deduction').read()[0]
        return action

    def button_config_deductions(self):
        """
        Button to go to Configuration Settings to set which deductions will be shown in chart.
        :return: action
        """
        self.ensure_one()
        action = self.env.ref('l10n_us_hr_payroll.action_us_payroll_configuration').read()[0]
        return action

    ####################################################################################################################
    # GRAPH DATA
    ####################################################################################################################
    @api.model
    def retrieve_payroll_dashboard(self, start, end, group_by, type=None):
        data = {'graph_data': [], 'info_data': [], 'extra_graph_setting': {}}
        query, params = self._sql_retrieve(type, start, end, group_by)

        result = []
        if query:
            self.env.cr.execute(query, params)
            result = self.env.cr.fetchall()

        if type == 'tbd':
            data = self._retrieve_deduction(result)
        elif type == 'hours':
            data = self._retrieve_working_time(result, start, end, group_by)
        elif type == 'gross':
            data = self._retrieve_grosspay_breakdowns(result)
        elif type == 'cost':
            data = self._retrieve_payroll_cost(result, start, end, group_by)

        return data

    def _sql_retrieve(self, type, start, end, group_by):
        """
        Create sql query for each type of dashboard record.
        :param type: 'tbd' / 'cost' / 'hours' / 'cost'
        :param start:
        :param end:
        :param group_by:
        :return: sql query
        """
        query = params = None
        if start and end:
            company_id = self.env.company
            frequency_id = company_id.pay_frequency_id
            extra_condition = """AND pp.pay_frequency_id = {}""".format(frequency_id.id) if frequency_id and start == end else ''
            conditions = """
                pp.company_id = {company} AND
                pp.pay_date BETWEEN '{start}' AND '{end}' AND
                pp.state = 'done'
                {extra}
            """.format(company=company_id.id, start=start, end=end, extra=extra_condition)
            order = ''
            sql_template = """SELECT {columns} FROM {table} WHERE {conditions} GROUP BY {group} {order}"""

            # Deductions
            if type == 'tbd':
                columns = """pr.id, SUM(ps.amount) AS total_ee, SUM(ps.er_dollar_amt) AS total_er"""
                table = """payroll_deduction pr
                    JOIN payslip_deduction ps ON pr.id = ps.deduction_id
                    JOIN pay_period pp ON ps.pay_period_id = pp.id
                """
                conditions += """AND pr.id IN %s"""
                group = """pr.id"""
                params = (tuple(company_id.chart_deduction_ids.ids or [-1]),)

            # Gross Pay Breakdowns
            elif type == 'gross':
                columns = """pr.id, pr.name, SUM(ps.amount) AS total_ee"""
                table = """payroll_compensation pr
                    JOIN payslip_compensation ps ON pr.id = ps.compensation_id
                    JOIN pay_period pp ON ps.pay_period_id = pp.id
                """
                group = """pr.id"""
                order = """ORDER BY total_ee DESC"""

            # Add group_by conditions
            else:
                if start == end or group_by == GROUP_BY_PERIOD['value']:
                    extra_select = """pp.id AS group_by, pp.name, pp.pay_date"""
                    group = """group_by, pp.pay_date"""
                    order = """ORDER BY pp.pay_date"""
                else:
                    group = """group_by"""
                    order = """ORDER BY group_by"""
                    if group_by == GROUP_BY_WEEK['value']:
                        extra_select = """DIV(CAST(EXTRACT(DAY from pp.pay_date) AS INT) - 1, 7) + 1 AS group_by"""
                    else:
                        extra_select = """date_part('{}', pp.pay_date::DATE) AS group_by""".format(group_by)
                table = """pay_period pp"""

                # Working Time Summary
                if type == 'hours':
                    columns = """
                        sum(total_regular + total_holiday) AS regular,
                        sum(total_overtime) AS overtime,
                        sum(total_double) AS double,
                        {extra}
                    """.format(extra=extra_select)

                # Payroll Cost
                else:
                    columns = """
                        sum(total_gross_pay) AS gross,
                        sum(total_er_tax) AS tax,
                        sum(total_er_deduction) AS deduction,
                        {extra}
                    """.format(extra=extra_select)

            query = sql_template.format(columns=columns, table=table, conditions=conditions, group=group, order=order)
        return query, params

    def _retrieve_deduction(self, result):
        """
        Retrieve graph data for `Deductions`.
        :param result: received from executing sql query.
        :return: graph data
        """
        deduction_ids = self.env.company.chart_deduction_ids

        ee_data, er_data = list(), list()
        graph_label = []
        index = 0

        for deduction_id in deduction_ids:
            _result = list(filter(lambda x: x[0] == deduction_id.id, result))
            ee_amount = sum(data[1] if data[1] else 0 for data in _result)
            er_amount = sum(data[2] if data[2] else 0 for data in _result)
            ee_data.append(ee_amount)
            er_data.append(er_amount)
            graph_label.append(deduction_id.name)

            index += 1

        info_data = {
            'total': [],
            'detail': [
                {'name': 'Employee Deduction', 'value': format_currency(self, sum(ee_data))},
                {'name': 'Company Contribution', 'value': format_currency(self, sum(er_data))},
            ]
        }

        graph_data = [
            get_barchart_format(self, ee_data, _('Employee'), GRAPH_COLOR['blue']),
            get_barchart_format(self, er_data, _('Company'), GRAPH_COLOR['orange']),
        ]

        return get_chart_json(self, graph_data, graph_label, get_chartjs_setting(chart_type='bar', stacked=True), info_data)

    def _retrieve_grosspay_breakdowns(self, result):
        """
        Retrieve graph data for `Gross Pay Breakdowns`.
        :param result: received from executing sql query.
        :return: graph data
        """
        model_env = self.env['ir.model.data']

        info_detail = []
        gross_data = []
        graph_label = []

        # Create summary data and graph data
        for data in result:
            compensation_id = model_env.search([('model', '=', 'payroll.compensation'), ('res_id', '=', data[0])], limit=1)
            external_id = compensation_id.name
            name = _('Regular Pay' if external_id == 'payroll_compensation_salary' else data[1])
            graph_label.append(name)
            info_detail.append({'name': name, 'value': data[2] if data[2] else 0})
            gross_data.append(data[2] if data[2] else 0)

        # Merge lines if number of line > MAX_LINES (4)
        if len(info_detail) > MAX_LINES:
            last_line = info_detail[MAX_LINES - 1]
            last_line['name'] = _('Others')
            while len(info_detail) > MAX_LINES:
                last_line['value'] += info_detail[MAX_LINES]['value']
                del info_detail[MAX_LINES]

        # Format value
        for line in info_detail:
            line['value'] = format_value(self, line['value'])

        info_data = {
            'total': [{'name': _('Total Gross Pay'), 'value': format_value(self, sum(gross_data))}],
            'detail': info_detail
        }
        background_color = (pieColor * ceil(len(graph_label)/len(pieColor)))[:len(graph_label)]
        graph_data = [get_piechart_format(gross_data, background_color)]

        return get_chart_json(self, graph_data, graph_label, get_chartjs_setting(chart_type='pie'), info_data)

    def _retrieve_working_time(self, result, start, end, group_by):
        """
        Retrieve graph data for `Hours per Pay Rate`.
        :param result: received from executing sql query.
        :return: graph data
        """
        grouped_data, graph_label = group_graph_data(result, start, end, group_by, length=3)

        data = [
            {'label': _('Regular Rate Hours'), 'value': grouped_data[0], 'color': GRAPH_COLOR['blue']},
            {'label': _('Overtime Rate Hours'), 'value': grouped_data[1], 'color': GRAPH_COLOR['orange']},
            {'label': _('Double Overtime Rate Hours'), 'value': grouped_data[2], 'color': GRAPH_COLOR['purple']}
        ]

        info_data = {
            'total': [{'name': _('Total Hours'), 'value': format_value(self, sum(sum(x['value']) for x in data), is_currency=False)}],
            'detail': [{'name': x['label'], 'value': format_value(self, sum(x['value']), is_currency=False)} for x in data]
        }

        graph_data = [get_barchart_format(self, x['value'], x['label'], x['color']) for x in data]

        setting = get_chartjs_setting(chart_type='bar', stacked=True)
        setting.update({'no_currency': True})

        return get_chart_json(self, graph_data, graph_label, setting, info_data)

    def _retrieve_payroll_cost(self, result, start, end, group_by):
        """
        Retrieve graph data for `Payroll Cost`.
        :param result: received from executing sql query.
        :return: graph data
        """
        grouped_data, graph_label = group_graph_data(result, start, end, group_by, length=3)

        data = [
            {'label': _('Gross Pay'), 'value': grouped_data[0], 'color': GRAPH_COLOR['blue']},
            {'label': _('Company Tax'), 'value': grouped_data[1], 'color': GRAPH_COLOR['orange']},
            {'label': _('Company Contribution'), 'value': grouped_data[2], 'color': GRAPH_COLOR['green']}
        ]

        info_data = {
            'total': [{'name': _('Total Cost'), 'value': format_value(self, sum(sum(x['value']) for x in data),)}],
            'detail': [{'name': x['label'], 'value': format_value(self, sum(x['value']))} for x in data]
        }

        graph_data = [get_barchart_format(self, x['value'], x['label'], x['color']) for x in data]

        return get_chart_json(self, graph_data, graph_label, get_chartjs_setting(chart_type='bar', stacked=True), info_data)
