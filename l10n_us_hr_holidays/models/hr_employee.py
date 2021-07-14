# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class Employee(models.Model):
    _inherit = 'hr.employee'

    # Technical fields
    outdated_holiday_leaves = fields.Boolean('Holiday Leaves Outdated', groups="hr.group_hr_user",
                                             help='Technical fields for handling public holiday leaves')

    def _get_work_state(self):
        return self.address_id.state_id or False

    def _update_outdated_holiday_leaves(self, values):
        # Raise outdated holiday leaves on Employee form if user changes Working State or Working Time
        if 'work_state_id' in values:
            self.filtered(lambda r: r.work_state_id.id != values['work_state_id']).write({'outdated_holiday_leaves': True})

        if 'resource_calendar_id' in values:
            self.filtered(lambda r: r.resource_calendar_id.id != values['resource_calendar_id']).write({'outdated_holiday_leaves': True})

    def write(self, values):
        self._update_outdated_holiday_leaves(values)
        return super().write(values)
