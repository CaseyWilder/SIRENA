from odoo import api, fields, models


class AlternateCalculation(models.Model):
    _name = 'alternate.calculation'
    _description = 'Alternate Tax Rate Table'

    vertex_id = fields.Char('Vertex ID')
    name = fields.Char('Description')
    tax_name = fields.Char('Tax Name')
    tax_id = fields.Char('Tax ID')
    school_dist = fields.Char('School District')

    @api.model
    def _name_search(self, name, args=None, operator='ilike', limit=100, name_get_uid=None):
        args = args or []
        domain = []
        if name:
            domain = [('name', operator, name)]
        if self.env.context.get('state_id', False):
            state_id = self.env['res.country.state'].browse(self.env.context['state_id'])
            if state_id:
                domain.append(('id', 'in', state_id.alternate_calculation_ids.ids))

        cal_ids = self._search(domain + args, limit=limit, access_rights_uid=name_get_uid)
        return self.browse(cal_ids).name_get()
