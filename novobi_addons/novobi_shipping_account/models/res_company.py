# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api


class ResCompany(models.Model):
    _inherit = 'res.company'

    def _default_shipment_mail_template(self):
        try:
            return self.env.ref('delivery.mail_template_data_delivery_confirmation').id
        except ValueError:
            return False

    shipment_email_template_id = fields.Many2one('mail.template', string='Shipment Email Template',
                                                 help="Shipment Email Template",
                                                 domain="[('model', '=', 'stock.picking')]",
                                                 default=_default_shipment_mail_template)

    shipping_label_options = fields.Selection(selection=[
        ('w_packing', 'with Packing Slip'),
        ('wo_packing', 'without Packing Slip')
    ], string='Shipping Label Printing Options', default='wo_packing')

    packing_slip_size = fields.Many2one('report.paperformat')
