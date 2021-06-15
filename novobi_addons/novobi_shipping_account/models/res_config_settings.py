# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    shipment_email_template_id = fields.Many2one('mail.template', related='company_id.shipment_email_template_id', readonly=False)
    shipping_label_options = fields.Selection(related='company_id.shipping_label_options', readonly=False)
    packing_slip_size = fields.Many2one('report.paperformat', domain=['|', ('name', '=', '4 x 6'), ('name', '=', '8.5 x 11')])

    @api.model
    def get_values(self):
        res = super(ResConfigSettings, self).get_values()
        company = self.env.company
        pl46 = self.env.ref('novobi_shipping_account.paperformat_packing_slip_4x6', False)
        res.update({
            'packing_slip_size': company.packing_slip_size.id or (pl46.id if pl46 else False),
        })
        return res

    def set_values(self):
        super(ResConfigSettings, self).set_values()
        self.env.company.update({
            'packing_slip_size': self.packing_slip_size.id,
        })
