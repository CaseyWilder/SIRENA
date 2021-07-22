from odoo import api, fields, models

from .address_mixin import EE_PARTNER_SYNC_FIELDS
from ..utils.utils import sync_record


class Partner(models.Model):
    _inherit = 'res.partner'

    county = fields.Char('County')
    employee_id = fields.Many2one('hr.employee', string='Employee', ondelete='cascade')
    # Change label because it has same label with "employee_id" field
    employee = fields.Boolean(string='Is an Employee')

    def sync_related_employee(self, values):
        """
        Sync the employee which has id = res_partner.employee_id
        """
        if self._context.get('sync_from_employee', False):
            return

        sync_employee_contact = self.env.company.sync_employee_contact
        sync_fields = set(values.keys()) & set(sync_employee_contact and EE_PARTNER_SYNC_FIELDS or ['name'])
        if not sync_fields:
            return

        for record in self.with_context(sync_from_partner=True):
            if record.employee_id:
                values = sync_record(record, sync_fields)
                record.employee_id.write(values)

    def write(self, vals):
        res = super(Partner, self).write(vals)
        self.sync_related_employee(vals)
        return res
