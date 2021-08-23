from datetime import timedelta


def get_timelog_template(field_ids, calculated_by):
    """
    Create timelog from App(Attendance/Timesheet) to analyze working hours.
    :param field_ids: recordset (attendance_ids/timesheet_ids)
    :param calculated_by: field containing working hours ('worked_hours' in Attendance, 'unit_amount' in Timesheet)
    :return: timelog: list of list(date, working hours, regular=working hours, overtime=0, double overtime=0)
    """
    # Create timelog
    timelog = list()
    field_ids = field_ids.filtered(lambda r: r[calculated_by] > 0)
    for record in field_ids:
        timelog.append([record.date, record[calculated_by], record[calculated_by], 0, 0])

    # Sort by date
    timelog.sort(key=lambda log: log[0])

    # Merge all logs having same date
    length, i = len(timelog) - 1, 0
    while i < length:
        if timelog[i + 1][0] == timelog[i][0]:
            timelog[i][1] += timelog[i + 1][1]
            timelog[i][2] += timelog[i + 1][2]
            del timelog[i + 1]
            length -= 1
        else:
            i += 1

    return timelog


def group_timelog_by_week(timelog, workweek, start_date, end_date):
    """
    Group all timelogs (include previous and current period) by week to calculate weekly overtime
    :param timelog: list of list(date, working hours, regular, overtime, double overtime)
    :param workweek: start of workweek (mon=0, tue=1, wed=2, ..., sun=6)
    :param start_date: start date of period
    :param end_date: end date of period
    :return: group_timelog: list of list(timelog)
    """
    group_timelog = list()
    temp = start_date.weekday()
    start = start_date - timedelta(days=temp - workweek if temp >= workweek else 7 + temp - workweek)

    while start <= end_date:
        group = list(filter(lambda log: start <= log[0] <= start + timedelta(days=6), timelog))
        group_timelog.append(group)
        start += timedelta(weeks=1)

    return group_timelog


def split_working_hours_per_week(timelog, weekly_ovt=40, daily_ovt=None, double_ovt=None, consecutive_7_days=False):
    """
    Split total working hours to regular pay, overtime pay and double overtime pay.
    :param timelog: list of list(date, working hours, regular=working hours, overtime=0, double overtime=0)
    :param weekly_ovt: will be overtime if working hours in a week is greater than this param.
    :param daily_ovt: will be overtime if working hours in a day is greater than this param.
    :param double_ovt: will be double overtime if working hours in a day is greater than this param.
    :param consecutive_7_days: if True, total working hours of 7th day in week is overtime.
    :return: timelog: after splitting working hours.
    """
    count = 0
    for log in timelog:
        log[4] = max(0, log[1] - double_ovt) if double_ovt else 0           # Calculate double overtime
        log[3] = max(0, log[1] - log[4] - daily_ovt) if daily_ovt else 0    # Calculate overtime
        log[2] = log[1] - log[3] - log[4]                                   # Calculate regular
        count += log[2]             # Sum of regular from the 1st day of week
        delta = count - weekly_ovt  # If it is greater than weekly overtime
        if delta > 0:
            log[2] -= delta         # That part will turn into overtime
            log[3] += delta
            count = weekly_ovt

    if consecutive_7_days and len(timelog) == 7:
        last_timelog = timelog[6]
        last_timelog[3] += last_timelog[2]
        last_timelog[2] = 0

    return timelog


def get_total_working_hours(timelog):
    """
    Get total working hours from timelog.
    :param timelog: list of list(date, working hours, regular, overtime, double overtime)
    :return: total working hours (regular + overtime + double)
    """
    return sum(log[1] for log in timelog)


def get_regular_hours(timelog):
    """
    Get regular hours from timelog.
    :param timelog: list of list(date, working hours, regular, overtime, double overtime)
    :return: total regular hours
    """
    return sum(log[2] for log in timelog)


def get_overtime_hours(timelog):
    """
    Get overtime hours from timelog.
    :param timelog: list of list(date, working hours, regular, overtime, double overtime)
    :return: total overtime hours
    """
    return sum(log[3] for log in timelog)


def get_double_overtime_hours(timelog):
    """
    Get daily double overtime hours from timelog.
    :param timelog: list of list(date, working hours, regular, overtime, double overtime)
    :return: total daily double overtime hours
    """
    return sum(log[4] for log in timelog)


def get_all_working_hours(field_ids, calculate_by, workweek, start_date, end_date,
                          weekly_ovt=40, daily_ovt=None, double_ovt=None, consecutive_7_days=False):
    """
    Get total, regular, overtime, double overtime hours from timelog after splitting working hours.

    :param field_ids: recordset (attendance_ids/timesheet_ids)
    :param calculate_by: field containing working hours ('worked_hours' in Attendance, 'unit_amount' in Timesheet)
    :param workweek: start of workweek (mon=0, tue=1, wed=2, ..., sun=6)
    :param start_date: start date of period
    :param end_date: end date of period
    :param weekly_ovt: will be overtime if working hours in a week is greater than this param.
    :param daily_ovt: will be overtime if working hours in a day is greater than this param.
    :param double_ovt: will be double overtime if working hours in a day is greater than this param.
    :param consecutive_7_days: if True, total working hours of 7th day in week is overtime.
    :return: sum of each type of overtime.
    """
    tl = get_timelog_template(field_ids, calculate_by)
    groups = group_timelog_by_week(tl, workweek, start_date, end_date)
    timelog = list()
    for group in groups:
        split_working_hours_per_week(group, weekly_ovt, daily_ovt, double_ovt, consecutive_7_days)
        timelog += group

    cur_timelog = list(filter(lambda log: log[0] >= start_date, timelog))
    total = get_total_working_hours(cur_timelog)
    regular = get_regular_hours(cur_timelog)
    overtime = get_overtime_hours(cur_timelog)
    double = get_double_overtime_hours(cur_timelog)

    return total, regular, overtime, double
