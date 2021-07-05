# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools.translate import _

REQUEST_HOUR_INTERVALS = [
    ('0',),     ('0.25', '12:15 AM'),   ('0.5',),   ('0.75', '12:45 AM'),
    ('1',),     ('1.25', '1:15 AM'),    ('1.5',),   ('1.75', '1:45 AM'),
    ('2',),     ('2.25', '2:15 AM'),    ('2.5',),   ('2.75', '2:45 AM'),
    ('3',),     ('3.25', '3:15 AM'),    ('3.5',),   ('3.75', '3:45 AM'),
    ('4',),     ('4.25', '4:15 AM'),    ('4.5',),   ('4.75', '4:45 AM'),
    ('5',),     ('5.25', '5:15 AM'),    ('5.5',),   ('5.75', '5:45 AM'),
    ('6',),     ('6.25', '6:15 AM'),    ('6.5',),   ('6.75', '6:45 AM'),
    ('7',),     ('7.25', '7:15 AM'),    ('7.5',),   ('7.75', '7:45 AM'),
    ('8',),     ('8.25', '8:15 AM'),    ('8.5',),   ('8.75', '8:45 AM'),
    ('9',),     ('9.25', '9:15 AM'),    ('9.5',),   ('9.75', '9:45 AM'),
    ('10',),    ('10.25', '10:15 AM'),  ('10.5',),  ('10.75', '10:45 AM'),
    ('11',),    ('11.25', '11:15 AM'),  ('11.5',),  ('11.75', '11:45 AM'),
    ('12',),    ('12.25', '0:15 PM'),   ('12.5',),  ('12.75', '0:45 PM'),
    ('13',),    ('13.25', '1:15 PM'),   ('13.5',),  ('13.75', '1:45 PM'),
    ('14',),    ('14.25', '2:15 PM'),   ('14.5',),  ('14.75', '2:45 PM'),
    ('15',),    ('15.25', '3:15 PM'),   ('15.5',),  ('15.75', '3:45 PM'),
    ('16',),    ('16.25', '4:15 PM'),   ('16.5',),  ('16.75', '4:45 PM'),
    ('17',),    ('17.25', '5:15 PM'),   ('17.5',),  ('17.75', '5:45 PM'),
    ('18',),    ('18.25', '6:15 PM'),   ('18.5',),  ('18.75', '6:45 PM'),
    ('19',),    ('19.25', '7:15 PM'),   ('19.5',),  ('19.75', '7:45 PM'),
    ('20',),    ('20.25', '8:15 PM'),   ('20.5',),  ('20.75', '8:45 PM'),
    ('21',),    ('21.25', '9:15 PM'),   ('21.5',),  ('21.75', '9:45 PM'),
    ('22',),    ('22.25', '10:15 PM'),  ('22.5',),  ('22.75', '10:45 PM'),
    ('23',),    ('23.25', '11:15 PM'),  ('23.5',),  ('23.75', '11:45 PM'),
]


class HrLeave(models.Model):
    _inherit = 'hr.leave'

    # Override to add more intervals to Request Hour From and Request Hour To
    request_hour_from = fields.Selection(selection_add=REQUEST_HOUR_INTERVALS)
    request_hour_to = fields.Selection(selection_add=REQUEST_HOUR_INTERVALS)

    public_holiday_line_id = fields.Many2one('hr.public.holidays.line', string='Public Holiday')
    is_public_holiday = fields.Boolean(string='Is Public Holiday', default=False)
    state_id = fields.Many2one('res.country.state', string='Related State', related='holiday_status_id.state_id', store=True)

    ####################################################################################################################
    # CONSTRAINTS
    ####################################################################################################################
    @api.constrains('date_from', 'date_to', 'state_id')
    def _check_date(self):
        """
        Override this function for handling multi-states
        """
        for holiday in self:
            employee_id = holiday.employee_id or False
            domain = [
                ('date_from', '<', holiday.date_to),
                ('date_to', '>', holiday.date_from),
                ('employee_id', '=', employee_id and employee_id.id),
                ('id', '!=', holiday.id),
                ('state', 'not in', ['cancel', 'refuse']),
            ]
            if holiday.state_id:
                work_state_id = employee_id and employee_id._get_work_state() or False
                domain += [('state_id', '=', work_state_id and work_state_id.id)]
            nholidays = self.search_count(domain)
            if nholidays:
                raise ValidationError(_('You can not have two leaves that overlaps on the same day.'))

    ####################################################################################################################
    # ONCHANGE, COMPUTE/INVERSE
    ####################################################################################################################
    @api.onchange('holiday_status_id')
    def _onchange_holiday_status_id(self):
        if self.holiday_status_id.public_holiday_id:
            self.is_public_holiday = True
            return {
                'domain': {
                    'public_holiday_line_id': [
                        ('year_id', '=', self.holiday_status_id.public_holiday_id.id)]
                }
            }
        self.is_public_holiday = False

        return {
            'domain': {
                'public_holiday_line_id': [('year_id', '=', False)]
            }
        }

    @api.onchange('public_holiday_line_id')
    def _onchange_living_address_id(self):
        if self.public_holiday_line_id:
            self.name = self.public_holiday_line_id.name
            self.request_date_from = self.public_holiday_line_id.date
            self.request_date_to = self.public_holiday_line_id.date
        else:
            # Description should be cleared if user remove public holiday
            self.name = False

    ####################################################################################################################
    # ACTION
    ####################################################################################################################
    def action_validate(self):
        """
        Override to:
        - Filter by state of holiday status (in case generate public holidays)
        - Fix domain for search conflicting leaves
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

    ####################################################################################################################
    # HELPER METHODS
    ####################################################################################################################
    def _get_number_of_days(self, date_from, date_to, employee_id):
        if self.holiday_status_id.exclude_public_holidays or not self.holiday_status_id:
            instance = self.with_context(
                employee_id=employee_id,
                exclude_public_holidays=True,
            )
        else:
            instance = self
        return super(HrLeave, instance)._get_number_of_days(date_from, date_to, employee_id)

    def _prepare_employees_holiday_values(self, employees):
        """
        Override to remove number_of_days condition.
        If a holiday is on the same day with employee's day off, work_days_data[employee.id]['days'] = 0. Then it
        will return empty list, and :meth:`~_prepare_holiday_values` will cause an error "Index out of range"
        """
        self.ensure_one()
        return [{
            'name': self.name,
            'holiday_type': 'employee',
            'holiday_status_id': self.holiday_status_id.id,
            'date_from': self.date_from,
            'date_to': self.date_to,
            'request_date_from': self.date_from,
            'request_date_to': self.date_to,
            'notes': self.notes,
            'parent_id': self.id,
            'employee_id': employee.id,
            'state': 'validate',
        } for employee in employees]

