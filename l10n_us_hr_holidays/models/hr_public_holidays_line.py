# Part of Odoo. See LICENSE file for full copyright and licensing details.
from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


class HrPublicHolidaysLine(models.Model):
    _name = 'hr.public.holidays.line'
    _description = 'Public Holidays Lines'
    _order = 'date, name desc'

    name = fields.Char('Name', required=True)
    date = fields.Date('Date', required=True)
    year_id = fields.Many2one('hr.public.holidays', string='Calendar Year', required=True, ondelete='cascade')
    state_id = fields.Many2one(related='year_id.state_id', store=True)
    company_id = fields.Many2one(related='year_id.company_id', store=True)

    @api.constrains('date', 'state_id')
    def _check_date_state(self):
        for line in self:
            line._check_date_state_one()

    def _check_date_state_one(self):
        if self.date.year != self.year_id.year:
            raise ValidationError(_('Dates of holidays should be the same year as the calendar year they are being assigned to'))

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

    def action_generate_leave_requests(self):
        """
        Generate and approve all leaves request for chosen public holidays.
        :return: action to show notification
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
        leave_ids = self.env['hr.leave'].sudo().with_context(leave_context).create(leave_values)
        leave_ids.sudo().with_context(leave_context).action_validate()

        # Prepare message content
        if holiday_names:
            if len(holiday_names) == 1:
                message = _('Time Off requests for "{}" have been generated and approved.'.format(holiday_names[0]))
            else:
                holiday_names = '- ' + '\n- '.join(holiday_names)
                message = _('Time Off requests for these public holidays have been generated and approved:\n' + holiday_names)
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

    def get_leave_request_values(self, leave_type, date_from=None):
        """
        Get list of values to create leave requests for company and list of name of public holidays.
        :param leave_type: record of hr.leave.type for this current calendar year.
        :param date_from: today
        :return: list of leave values, list of holiday names
        """
        date_from = date_from or fields.Date.context_today(self)
        leave_values = []
        holiday_names = []

        for holiday_id in self.filtered(lambda r: r.date > date_from):
            dt = holiday_id.date
            holiday_names.append(holiday_id.name)
            leave_values.append({
                'date_from': dt,
                'date_to': dt + timedelta(days=1),
                'request_date_from_period': 'am',
                'employee_id': False,
                'report_note': False,
                'request_unit_custom': False,
                'category_id': False,
                'department_id': False,
                'payslip_status': False,
                'request_unit_hours': False,
                'request_unit_half': False,
                'request_hour_to': False,
                'message_attachment_count': 0,
                'name': holiday_id.name,
                'request_hour_from': False,
                'holiday_status_id': leave_type.id,
                'holiday_type': 'company',
                'mode_company_id': holiday_id.company_id.id,
                'number_of_days': 1,
                'request_date_from': dt,
                'request_date_to': dt,
                'state': 'confirm',
            })

        return leave_values, holiday_names

