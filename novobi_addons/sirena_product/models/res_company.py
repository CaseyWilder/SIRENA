from odoo import models, fields, api


class ResCompany(models.Model):
    _inherit = 'res.company'

    hide_shared_products = fields.Boolean(default=False)

    @api.model
    def init_hide_shared_products(self):
        company = self.env.ref('sirena_base.paradise', raise_if_not_found=False)
        if company:
            company.hide_shared_products = True
