from odoo import api, fields, models
from odoo.osv import expression


class FilingStatus(models.Model):
    _name = 'filing.status'
    _description = 'Filing Status'

    vertex_id = fields.Char('Vertex ID')
    name = fields.Char('Filing Status Description')
    is_federal = fields.Boolean('Belong to Federal', default=False)

    @api.model
    def _name_search(self, name, args=None, operator='ilike', limit=100, name_get_uid=None):
        args = args or []
        domain = []
        if name:
            domain = [('name', operator, name)]
        if 'use_w4_2020' in self._context:
            domain.append(('vertex_id', 'not in' if self._context['use_w4_2020'] else 'in', ['1', '2']))
        if self.env.context.get('state_id', False):
            state_id = self.env['res.country.state'].browse(self.env.context['state_id'])
            if state_id:
                domain.append(('id', 'in', state_id.filing_status_ids.ids))

        return self._search(expression.AND([domain, args]), limit=limit, access_rights_uid=name_get_uid)
