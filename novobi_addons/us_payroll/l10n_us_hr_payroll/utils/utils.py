from datetime import date
from pytz import timezone, utc

from odoo.tools.float_utils import float_compare, float_round

PAYABLE_CODE_PREFIX = '111'
EXPENSE_CODE_PREFIX = '212'
NO_DIGITS = 6

# Fields to track compensation
COMPENSATION_TRACKED_FIELDS = ['amount']

# Fields to track deduction
DEDUCTION_TRACKED_FIELDS = [
    'ee_amount_type', 'ee_amount', 'ee_max_amount_type', 'ee_max_amount', 'ee_maximum_period',
    'er_amount_type', 'er_amount', 'maximum_amount', 'maximum_period', 'owed_employee_remaining_amount'
]

# Confidential fields for Payroll
PAYROLL_CONFIDENTIAL_FIELDS = {
    'employee_type', 'pay_frequency_id', 'time_tracking_id', 'payment_method', 'checkin_method',

    'exempt_social_security', 'exempt_federal_tax', 'exempt_medicare',
    'alternate_calculation_id', 'work_alternate_calculation_id',

    'is_same_state', 'is_same_county', 'is_same_city',

    'fed_filing_status_id', 'fed_allow', 'fed_add_wh',
    'use_w4_2020', 'multiple_jobs', 'claim_dependents', 'other_income', 'other_deduction',
    'state_pri_allow', 'state_sec_allow', 'state_add_wh', 'filing_status_id',
    'county_allow', 'county_add_wh', 'city_allow', 'city_add_wh',

    'work_state_pri_allow', 'work_state_sec_allow', 'work_state_add_wh', 'work_filing_status_id',
    'work_county_allow', 'work_county_add_wh', 'work_city_allow', 'work_city_add_wh',

    'salary_amount', 'salary_period', 'calculate_salary_by'
}


def get_default_date_format(self):
    lang = self.env.company.partner_id.lang or 'en_US'
    lang_obj = self.env['res.lang']._lang_get(lang)
    return lang_obj.date_format


def convert_time_zone(dt, tz):
    if not isinstance(dt, date):
        return False

    # As default, Database always store datetime in UTC
    utc_dt = dt.replace(tzinfo=utc)
    return utc_dt.astimezone(timezone(tz))


def sync_record(record, values, sync_fields):
    """
    Check if new values are different from synchronized record's => return those values.
    :param record:      record needs to be synchronized.
    :param values:      new values
    :param sync_fields: field names need to be synchronized
    :return: sync:
    """
    sync = dict()
    for field in values:
        if field in sync_fields:
            if not record:
                # Create new res_partner
                sync[field] = values[field]
            else:
                # Only sync values which are changed
                if record[field] != values[field]:
                    try:
                        if record[field].id != values[field]:
                            sync[field] = values[field]
                    except AttributeError:
                        sync[field] = values[field]
    return sync


def get_min_value(value_1, value_2, precision_digits=2):
    return value_1 if float_compare(value_1, value_2, precision_digits) == -1 else value_2


def _get_tracked_field(method, model):
    todo, field, title = method.capitalize() + 'd', '', ''

    if model == 'employee.deduction':
        field = 'deduction_id'
        title = 'Deduction'
    elif model == 'employee.compensation':
        field = 'compensation_id'
        title = 'Additional Earning'

    return todo, title, field


def _convert_value(record, value, field):
    """
    Convert value of selection to string of selection
    :param record:
    :param value: value of field
    :param field: field to convert
    :return: converted_value
    """
    try:
        converted_value = dict(record._fields[field].selection).get(value)
    except AttributeError:
        converted_value = value
    return converted_value


def _convert_dict_values(list_fields, record, values):
    """
    Get fields need to be tracked and get string of selection fields.
    :param record:
    :param values:
    :return: converted_values
    """
    return {
        field: _convert_value(record, values[field], field) for field in values if field in list_fields
    }


def _get_tracked_message(method, record, tracked_field, values):
    list_field = COMPENSATION_TRACKED_FIELDS if tracked_field == 'compensation_id' else DEDUCTION_TRACKED_FIELDS

    message = '<ul>'
    arrow = '<span class="fa fa-long-arrow-right" role="img" aria-label="Changed" title="Changed"/>'
    if method == 'update':
        values = _convert_dict_values(list_field, record, values)
        for field, value in values.items():
            old_value = _convert_value(record, record[field], field)
            message += '<li>{}: {} {} {}</li>'.format(record._fields[field].string, old_value, arrow, value)
    else:
        for field in list_field:
            if record[field]:
                value = _convert_value(record, record[field], field)
                message += '<li>{}: {}</li>'.format(record._fields[field].string, value)
    message += '</ul>'

    return message


def track_one2many(method, obj, values=None):
    todo, title, tracked_field = _get_tracked_field(method, obj._name)

    if tracked_field:
        for record in obj:
            employee_id = record.employee_id
            if employee_id:
                related_id = record[tracked_field]
                message = '<p>{} {} {}</p>'.format(title, related_id.display_name, todo)
                message += _get_tracked_message(method, record, tracked_field, values)
                employee_id.message_post(body=message, subtype_xmlid='l10n_us_hr_payroll.mt_employee_confidential_message')


def calculate_current_period(pay_frequency_id, pay_date):
    if pay_frequency_id:
        frequency = int(pay_frequency_id.frequency)

        # Weekly - Return order of week.
        # Example: 26 -> 26
        if frequency == 52:
            return pay_date.isocalendar()[1]

        # Bi-weekly - Return order of week/2.
        # Example: (23 -> 12, 25 -> 13) ; (24 -> 12, 26 -> 13)
        elif frequency == 26:
            week = pay_date.isocalendar()[1]
            return float_round(value=week / 2, precision_digits=0, rounding_method='UP')

        # Semi-monthly
        # Example: first_pay_date = 18.05.2019 and second_pay_date = 02.06.2019
        #       5:  ----------------------------  -  18.05.2019 -> 2*(5-1)+2 = 10
        #       6:  02.06.2019 -> 2*(6-1)+1 = 11  -  18.06.2019 -> 2*(6-1)+2 = 12
        elif frequency == 24:
            first_pay = pay_frequency_id.first_pay_date
            second_pay = pay_frequency_id.second_pay_date
            if first_pay.month == second_pay.month:
                period_nth = 1 if pay_date.day == first_pay.day else 2
            else:
                period_nth = 2 if pay_date.day == first_pay.day else 1
            return 2 * (pay_date.month - 1) + period_nth

        # Monthly - Return order of month.
        # Example: 7 -> 7.
        elif frequency == 12:
            return pay_date.month


def split_confidential_tracked_fields(tracked_fields):
    """
    Split all tracked fields into 2 dict: confidential (in Payroll) and normal (in Employee).
    :param tracked_fields: all fields having param tracking=True
    :return: confidential_fields, normal_fields
    """

    return tracked_fields & PAYROLL_CONFIDENTIAL_FIELDS, tracked_fields - PAYROLL_CONFIDENTIAL_FIELDS


def is_valid_routing_number(routing_number):
    """
    This function will check whether the given value is a valid bank routing number, which will pass these constraints:
    # String length must be exactly 9
    # Contains only digits
    # Every digit collaborates each other by a specified rule
    :param routing_number: a string needs validating
    :return: True if passed or False otherwise
    """
    n, i, m = routing_number, isinstance, lambda v: v[0] * v[1]  # shorter aliases
    return i(n, str) and len(n) == 9 and n.isdigit() and sum(map(m, zip(map(int, n), [3, 7, 1] * 3))) % 10 == 0


def _standardize_vals(env, model, datas):
    """
    Remove fields that are not present in this model
    :param env: self.env
    :param model: name of current model
    :param datas: vals
    :return: updated vals
    """
    try:
        vals = datas.copy()
        for key in list(datas.keys()):
            if key not in env[model]._fields:
                del vals[key]
        return vals
    except Exception as e:
        print(e)
        return datas
