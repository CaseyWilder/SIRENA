import holidays as hl

from odoo import api, fields, models, _


class HrPublicHolidays(models.Model):
    _inherit = 'hr.public.holidays'

    @api.model
    def init_public_holidays(self):
        self.env['ir.config_parameter'].sudo().set_param('judson_holiday.lifespan', [
            'New Year\'s Day',
            'Memorial Day',
            'Independence Day',
            'Labor Day',
            'Thanksgiving',
            'Friday After Thanksgiving'
            'Christmas Day'
        ])

    def action_generate_default_holidays(self, create_leave_type=True):
        """
        Override to handle specific case of Judson Studios:
        - State is California, but include some holiday(s) in other state (e.g 'Good Friday' in Texas)
        - Apply observed day (default=false -> true)
        :param create_leave_type:
        """
        for record in self.filtered(lambda r: r.country_id.code == 'US'):
            # --- Customize ---
            state_code = 'TX'   # Hard code, instead of `record.state_id.code`
            default_holidays = hl.US(state=state_code, years=record.year, observed=True)
            # TODO: Remove New Year's Day (Observed) in the current calendar (or next calendar, choose 1 of them)?
            # --- Customize ---

            holidays = self._get_specific_holidays(default_holidays)

            record.line_ids = [(0, 0, {
                'name': holiday_name,
                'date': dt,
            }) for dt, holiday_name in holidays.items()]

            # Create leave type
            if create_leave_type:
                record._create_leave_type()

    def _get_specific_holidays(self, raw_state_holidays):
        """
        Override to only select allowed holidays given in sirena_holiday.lifespan
        :param raw_state_holidays: {datetime: "holiday name"}
        :return: state_holidays: {datetime: "holiday name"}
        """
        allowed_holidays = self.env['ir.config_parameter'].sudo().get_param('judson_holiday.lifespan')

        if not allowed_holidays:
            return raw_state_holidays

        return {
            key: value for key, value in raw_state_holidays.items() if value.replace(' (Observed)', '') in allowed_holidays
        }
