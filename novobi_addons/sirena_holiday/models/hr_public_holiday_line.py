from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError


class HrPublicHolidaysLine(models.Model):
    _inherit = 'hr.public.holidays.line'

    def _check_date_state_one(self):
        # Override to remove this condition, because we switch to use observed day.
        # E.g for New Year's Day, it could belong to the previous year.
        # if self.date.year != self.year_id.year:
        #     raise ValidationError(_('Dates of holidays should be the same year as the calendar year they are being assigned to'))

        domain = [
            ('date', '=', self.date),
            ('year_id', '=', self.year_id.id),
            ('id', '!=', self.id),
        ]

        if self.state_id:
            domain.append(('state_id', '=', self.state_id.id))
            if self.search_count(domain):
                raise ValidationError(_('You cannot create duplicate public holiday per date {} and one of the country states.'.format(self.date)))
        else:
            domain.append(('state_id', '=', False))
            if self.search_count(domain):
                raise ValidationError(_('You cannot create duplicate public holiday per date {}.'.format(self.date)))

    def get_leave_request_values(self, leave_type, date_from=None):
        """
        Override to add `public_holiday_line_id` to the time off request
        Fix timezone as well.
        """
        date_from = date_from or fields.Date.context_today(self)
        leave_values = []
        holiday_names = []

        for holiday_id in self.filtered(lambda r: r.date > date_from):
            dt = holiday_id.date
            holiday_names.append(holiday_id.name)
            leave_values.append({
                'name': holiday_id.name,
                'holiday_type': 'company',
                'holiday_status_id': leave_type.id,
                'is_public_holiday': True,
                'public_holiday_line_id': holiday_id.id,
                'request_date_from': dt,
                'request_date_to': dt,
                'mode_company_id': holiday_id.company_id.id,
                'state': 'confirm',
            })

        return leave_values, holiday_names

    def action_generate_leave_requests(self):
        """
        Override to approve before validate.
        We need change to `approve` first to let odoo calculate hours displayed.
        """
        if not self:
            return

        year_id = self.mapped('year_id')
        if len(year_id) != 1:
            raise UserError(_('Make sure you have chosen all holidays belonging to one calendar year.'))

        leave_type = self.env['hr.leave.type'].get_public_holiday_leave_type(year_id.id)
        today = fields.Date.context_today(self)
        leave_context = {
            'tracking_disable': True,
            'mail_activity_automation_skip': True,
            'leave_fast_create': True,
            'leave_skip_state_check': True
        }

        # Prepare list containing dict of leave values (still missing 'mode_company_id')
        leave_values, holiday_names = self.get_leave_request_values(leave_type=leave_type, date_from=today)

        # Create leave requests for Company and approve for all its employees
        leave_env = self.env['hr.leave'].sudo().with_context(leave_context)
        new_values = []

        for value in leave_values:
            new_leave = leave_env.new(value)
            new_leave._compute_date_from_to()
            new_values.append(new_leave._convert_to_write(new_leave._cache))

        leave_ids = leave_env.create(new_values).sudo().with_context(leave_context)
        leave_ids.action_validate()

        # Prepare message content
        if holiday_names:
            if len(holiday_names) == 1:
                message = _('Time Off requests for "{}" have been generated and approved.'.format(holiday_names[0]))
            else:
                holiday_names = '- ' + '\n- '.join(holiday_names)
                message = _(
                    'Time Off requests for these public holidays have been generated and approved:\n' + holiday_names)
        else:
            message = _('No Time Off request is generated for now.')

        # Return notification action
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Action Done'),
                'type': 'success',
                'message': message,
                'sticky': True,
                'next': {'type': 'ir.actions.act_window_close'},
            }
        }

    def name_get(self):
        return [(record.id, record.name + ' ({})'.format(record.date)) for record in self]
