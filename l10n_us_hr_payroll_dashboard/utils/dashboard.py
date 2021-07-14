from datetime import datetime, date
from dateutil.relativedelta import relativedelta

from odoo.tools import formatLang

BY_PERIOD = "period"
BY_MONTH = "month"
BY_QUARTER = "quarter"
BY_YEAR = "year"
BY_LAST_MONTH = "last_month"
BY_LAST_QUARTER = "last_quarter"
BY_LAST_YEAR = "last_year"

GROUP_BY_PERIOD = {'name': 'By Period', 'value': 'period'}
GROUP_BY_WEEK = {'name': 'By Week', 'value': 'week'}
GROUP_BY_MONTH = {'name': 'By Month', 'value': 'month'}
GROUP_BY_QUARTER = {'name': 'By Quarter', 'value': 'quarter'}
GROUP_BY_YEAR = {'name': 'By Year', 'value': 'year'}

GROUP_BY = {
    BY_PERIOD: [],
    BY_MONTH: [GROUP_BY_PERIOD, GROUP_BY_WEEK, GROUP_BY_MONTH],
    BY_QUARTER: [GROUP_BY_MONTH, GROUP_BY_QUARTER],
    BY_YEAR: [GROUP_BY_MONTH, GROUP_BY_QUARTER, GROUP_BY_YEAR],
    BY_LAST_MONTH: [GROUP_BY_PERIOD, GROUP_BY_WEEK, GROUP_BY_MONTH],
    BY_LAST_QUARTER: [GROUP_BY_MONTH, GROUP_BY_QUARTER],
    BY_LAST_YEAR: [GROUP_BY_MONTH, GROUP_BY_QUARTER, GROUP_BY_YEAR]
}

GRAPH_COLOR = {
    'blue': '#649ce7',
    'orange': '#f19848',
    'green': '#00A09D',
    'purple': '#875a7b',
    'silver': '#C0C0C0',
    'lightgreen': '#afd393',
}

GROSSPAY_COLOR = {
    'payroll_compensation_salary': GRAPH_COLOR['blue'],
    'payroll_compensation_holiday': GRAPH_COLOR['orange'],
    'payroll_compensation_sick': GRAPH_COLOR['purple'],
    'payroll_compensation_vacation': GRAPH_COLOR['silver']
}


def format_currency(self, value):
    currency = self.env.company.currency_id
    return_value = formatLang(self.env, currency.round(value) + 0.0, currency_obj=currency)
    return return_value


def format_value(self, value, is_currency=True):
    return format_currency(self, value) if is_currency else '{:,.2f}'.format(value)


def get_json_render(data_type, extend, data_render, name_card, selection, function_retrieve, extra_param, extra_graph_setting={}):
    return {
        'function_retrieve': function_retrieve,
        'data_type': data_type,
        'extend': extend,
        'data_render': data_render,
        'name': name_card,
        'selection': selection,
        'extra_param': extra_param,
        'extra_graph_setting': extra_graph_setting
    }


def get_json_data_for_selection(self, selection):
    """
    Get json data for each option of time_filter
    :param self: payroll.dashboard object
    :param selection:
    :return: selection
    """
    time_filter = self.time_filter
    default_selection = self.default_time_filter
    today = date.today()
    for time in time_filter:
        start, end = get_period_filter(self, today, time['type'], time['delta'])
        time_selection = {
            'name': time['name'],
            'start': start.strftime('%Y-%m-%d') if start else False,
            'end': end.strftime('%Y-%m-%d') if end else False,
            'default': time['type'] == default_selection,
            'separate': time['separate'],
            'group_by': GROUP_BY[time['type']]
        }
        selection.append(time_selection)


def get_period_filter(self, date_value, time_filter_type, time_delta):
    """
    Get period filter (start date, end date) based on its type.
    :param self: payroll.dashboard object
    :param date_value: current date
    :param time_filter_type: By_PERIOD, BY_MONTH, BY_QUARTER, BY_YEAR...
    :param time_delta: 0 (current month/quarter/year) or -1 (last month/quarter/year)
    :return: start, end
    """
    start, end = None, None
    if date_value and time_filter_type:
        year = date_value.year
        month = date_value.month
        if time_filter_type == BY_PERIOD:
            company_id = self.env.company
            frequency_id = company_id.pay_frequency_id
            if frequency_id:
                query = """
                    SELECT pay_date
                    FROM pay_period
                    WHERE
                        company_id = {} AND
                        pay_frequency_id = {} AND
                        pay_date <= '{}' AND
                        state = 'done'
                    ORDER BY pay_date DESC
                    LIMIT 1
                """.format(company_id.id, frequency_id.id, date_value)
                self.env.cr.execute(query)
                res = self.env.cr.fetchall()
                start = end = res[0][0] if res else False
        elif time_filter_type in [BY_MONTH, BY_LAST_MONTH]:
            start = datetime(year, month, 1) + relativedelta(months=time_delta)
            end = start + relativedelta(months=1, days=-1)
        elif time_filter_type in [BY_QUARTER, BY_LAST_QUARTER]:
            month = int((month - 1) / 3) * 3 + 1
            start = datetime(year, month, 1) + relativedelta(months=time_delta * 3)
            end = start + relativedelta(months=3, days=-1)
        elif time_filter_type in [BY_YEAR, BY_LAST_YEAR]:
            start = datetime(year, 1, 1) + relativedelta(years=time_delta)
            end = start + relativedelta(years=1, days=-1)
    return start, end


def get_period_group_by(start, end, group_by):
    """
    Group time filter into multiple period based on group_by
    :param start:
    :param end:
    :param group_by:
    :return: dict('start', 'end', 'value', 'name')
    """
    def append_to_return_values(start, end, value, name):
        return_values.append({
            'start': start,
            'end': end,
            'value': value,
            'name': name
        })

    return_values = []
    # No group by (Last Scheduled Period) or Group by Period
    if not group_by and start == end or group_by == GROUP_BY_PERIOD['value']:
        append_to_return_values(start, end, False, False)

    # Group by Week
    elif group_by == GROUP_BY_WEEK['value']:
        value = 1
        while start <= end:
            _end = start + relativedelta(days=min(6, (end - start).days))
            name = start.strftime("%b %d") + ' - ' + _end.strftime("%d")
            append_to_return_values(start, _end, value, name)
            value += 1
            start += relativedelta(days=7)

    # Group by Month
    elif group_by == GROUP_BY_MONTH['value']:
        while start <= end:
            _end = start + relativedelta(months=1, days=-1)
            append_to_return_values(start, _end, start.month, start.strftime("%b"))
            start += relativedelta(months=1)

    # Group by Quarter
    elif group_by == GROUP_BY_QUARTER['value']:
        while start <= end:
            quarter = int((start.month - 1) / 3) + 1
            _end = start + relativedelta(months=3, days=-1)
            name = 'Q{} {}'.format(quarter, start.year)
            append_to_return_values(start, _end, quarter, name)
            start += relativedelta(months=3)

    # Group by Year
    elif group_by == GROUP_BY_YEAR['value']:
        append_to_return_values(start, end, start.year, '{}'.format(start.year))

    return return_values


def group_graph_data(query_result, start, end, groupby, length):
    periods = []
    graph_label = []
    grouped_data = []
    for i in range(length):
        grouped_data.append([])

    if start and end:
        # Convert string to datetime
        start = datetime.strptime(start, '%Y-%m-%d')
        end = datetime.strptime(end, '%Y-%m-%d')

        # If filter by `Last Scheduled Period` or group by `By Period`.
        if start == end or groupby == GROUP_BY_PERIOD['value']:
            periods += ({
                'value': data[length],
                'name': data[length + 1]
            } for data in query_result)
        else:
            periods = get_period_group_by(start, end, groupby)

        for period in periods:
            graph_label.append(period['name'])
            matched_period = list(filter(lambda x: x[length] == period['value'], query_result))
            for index in range(length):
                grouped_data[index].append(sum(x[index] if x[index] else 0 for x in matched_period))

    return grouped_data, graph_label
