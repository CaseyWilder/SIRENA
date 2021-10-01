from datetime import timedelta

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from odoo.tools.float_utils import float_compare


class HrLeave(models.Model):
    _inherit = 'hr.leave'

    @api.constrains('state', 'number_of_days', 'holiday_status_id')
    def _check_holidays(self):
        """
        Override to fix issue when refuse a time off request with company mode
        :return:
        """
        mapped_days = self.mapped('holiday_status_id').get_employees_days(self.mapped('employee_id').ids)

        for holiday in self:
            if holiday.holiday_type != 'employee' or not holiday.employee_id or holiday.holiday_status_id.allocation_type == 'no':
                continue
            leave_days = mapped_days.get(holiday.employee_id.id, {}).get(holiday.holiday_status_id.id, False)
            if not leave_days:
                continue

            if (
                    float_compare(leave_days['remaining_leaves'], 0, precision_digits=2) == -1 or
                    float_compare(leave_days['virtual_remaining_leaves'], 0, precision_digits=2) == -1
            ):
                raise ValidationError(_('The number of remaining time off is not sufficient for this time off type.\n'
                                        'Please also check the time off waiting for validation.'))

    def _prepare_employees_holiday_values(self, employees):
        """
        If create public holidays for employee, do not add 'date_from' and 'date_to'.
        """
        self.ensure_one()
        leaves = [{
            'name': self.name,
            'holiday_type': 'employee',
            'holiday_status_id': self.holiday_status_id.id,
            'is_public_holiday': bool(self.public_holiday_line_id),
            'public_holiday_line_id': self.public_holiday_line_id.id,
            'request_date_from': self.request_date_from,
            'request_date_to': self.request_date_from,
            'notes': self.notes,
            'parent_id': self.id,
            'employee_id': employee.id,
        } for employee in employees]

        extra_val = {
            'date_from': self.date_from,
            'date_to': self.date_to,
            'state': 'validate'
        } if not self.public_holiday_line_id else {'state': 'confirm'}

        for leave in leaves:
            leave.update(extra_val)

        return leaves

    def action_validate(self):
        """
        Override to approve employee request which are generated from company mode.
        """
        current_employee = self.env.user.employee_id
        leaves = self.filtered(lambda l: l.employee_id and not l.number_of_days)
        if leaves:
            employee_names = ', '.join(leaves.mapped('employee_id.name'))
            raise ValidationError(_('The following employees are not supposed to work during that period:\n {}'.format(employee_names)))

        if any(holiday.state not in ['confirm', 'validate1'] and holiday.validation_type != 'no_validation' for holiday in self):
            raise UserError(_('Time off request must be confirmed in order to approve it.'))

        self.write({'state': 'validate'})
        self.filtered(lambda holiday: holiday.validation_type == 'both').write({'second_approver_id': current_employee.id})
        self.filtered(lambda holiday: holiday.validation_type != 'both').write({'first_approver_id': current_employee.id})

        for holiday in self.filtered(lambda holiday: holiday.holiday_type != 'employee'):
            if holiday.holiday_type == 'category':
                employees = holiday.category_id.employee_ids
            elif holiday.holiday_type == 'company':
                # PAYROLL-265: filter by state of holiday status (in case generate public holidays)
                domain = [('company_id', '=', holiday.mode_company_id.id)]
                if holiday.holiday_status_id.state_id:
                    domain += [('work_state_id', '=', holiday.holiday_status_id.state_id.id)]
                employees = self.env['hr.employee'].search(domain)
            else:
                employees = holiday.department_id.member_ids

            conflicting_leaves = self.env['hr.leave'].with_context(
                tracking_disable=True,
                mail_activity_automation_skip=True,
                leave_fast_create=True
            ).search([
                ('date_from', '<', holiday.date_to),    # PAYROLL-408: Consecutive Public Holidays will be overlapped -> change from '<=' to '<'
                ('date_to', '>', holiday.date_from),
                ('state', 'not in', ['cancel', 'refuse']),
                ('holiday_type', '=', 'employee'),
                ('employee_id', 'in', employees.ids)])

            if conflicting_leaves:
                # YTI: More complex use cases could be managed in master
                if holiday.leave_type_request_unit != 'day' or any(l.leave_type_request_unit == 'hour' for l in conflicting_leaves):
                    raise ValidationError(_('You can not have 2 time off that overlaps on the same day.'))

                # keep track of conflicting leaves states before refusal
                target_states = {l.id: l.state for l in conflicting_leaves}
                conflicting_leaves.action_refuse()
                split_leaves_vals = []
                for conflicting_leave in conflicting_leaves:
                    if conflicting_leave.leave_type_request_unit == 'half_day' and conflicting_leave.request_unit_half:
                        continue

                    # Leaves in days
                    if conflicting_leave.date_from < holiday.date_from:
                        before_leave_vals = conflicting_leave.copy_data({
                            'date_from': conflicting_leave.date_from.date(),
                            'date_to': holiday.date_from.date() + timedelta(days=-1),
                            'state': target_states[conflicting_leave.id],
                        })[0]
                        before_leave = self.env['hr.leave'].new(before_leave_vals)
                        before_leave._compute_date_from_to()

                        # Could happen for part-time contract, that time off is not necessary
                        # anymore.
                        # Imagine you work on monday-wednesday-friday only.
                        # You take a time off on friday.
                        # We create a company time off on friday.
                        # By looking at the last attendance before the company time off
                        # start date to compute the date_to, you would have a date_from > date_to.
                        # Just don't create the leave at that time. That's the reason why we use
                        # new instead of create. As the leave is not actually created yet, the sql
                        # constraint didn't check date_from < date_to yet.
                        if before_leave.date_from < before_leave.date_to:
                            split_leaves_vals.append(before_leave._convert_to_write(before_leave._cache))
                    if conflicting_leave.date_to > holiday.date_to:
                        after_leave_vals = conflicting_leave.copy_data({
                            'date_from': holiday.date_to.date() + timedelta(days=1),
                            'date_to': conflicting_leave.date_to.date(),
                            'state': target_states[conflicting_leave.id],
                        })[0]
                        after_leave = self.env['hr.leave'].new(after_leave_vals)
                        after_leave._compute_date_from_to()
                        # Could happen for part-time contract, that time off is not necessary
                        # anymore.
                        if after_leave.date_from < after_leave.date_to:
                            split_leaves_vals.append(after_leave._convert_to_write(after_leave._cache))

                split_leaves = self.env['hr.leave'].with_context(
                    tracking_disable=True,
                    mail_activity_automation_skip=True,
                    leave_fast_create=True,
                    leave_skip_state_check=True
                ).create(split_leaves_vals)

                split_leaves.filtered(lambda l: l.state in 'validate')._validate_leave_request()

            values = holiday._prepare_employees_holiday_values(employees)

            if holiday.public_holiday_line_id:
                leave_env = self.env['hr.leave'].with_context(
                    tracking_disable=True,
                    mail_activity_automation_skip=True,
                    leave_fast_create=True,
                    leave_skip_state_check=True,
                ).sudo()
                new_values = []

                for val in values:
                    leave = leave_env.new(val)
                    leave._compute_date_from_to()
                    new_values.append(leave._convert_to_write(leave._cache))

                leaves = leave_env.create(new_values)
                leaves.action_approve()

            else:
                leaves = self.env['hr.leave'].with_context(
                    tracking_disable=True,
                    mail_activity_automation_skip=True,
                    leave_fast_create=True,
                    leave_skip_state_check=True,
                ).create(values)

            leaves._validate_leave_request()

        employee_requests = self.filtered(lambda hol: hol.holiday_type == 'employee')
        employee_requests._validate_leave_request()
        if not self.env.context.get('leave_fast_create'):
            employee_requests.filtered(lambda holiday: holiday.validation_type != 'no_validation').activity_update()
        return True
