from odoo import api, fields, models

from .address_mixin import EE_PARTNER_SYNC_FIELDS
from ..utils.utils import sync_record


class Partner(models.Model):
    _inherit = 'res.partner'

    county = fields.Char('County')
    employee_id = fields.Many2one('hr.employee', string='Employee')
    # Change label because it has same label with "employee_id" field
    employee = fields.Boolean(string='Is an Employee')

    def sync_related_employee(self, values):
        """
        Sync the employee which has id = res_partner.employee_id
        """
        for record in self:
            if record.employee_id:
                values = sync_record(record.employee_id, values, EE_PARTNER_SYNC_FIELDS)
                if values:
                    record.employee_id.write(values)

    def write(self, vals):
        res = super(Partner, self).write(vals)
        if self._context.get('from_employee', False) != '1':
            self.with_context(from_partner='1').sync_related_employee(vals)
        return res
