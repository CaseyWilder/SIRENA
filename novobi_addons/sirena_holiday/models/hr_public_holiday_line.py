from odoo import models, api


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
