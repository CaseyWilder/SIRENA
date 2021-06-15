# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api, _


class StockServiceImmediateTransfer(models.TransientModel):
    _name = 'confirm.create.shipping.label'
    _description = 'Check creating shipping label confirmation when validate Delivery Order'

    picking_id = fields.Many2one('stock.picking')

    def confirm_yes(self):
        self.ensure_one()
        return self.picking_id.with_context(validate_do=True, is_confirm_wiz=True).open_create_label_form()

    def confirm_no(self):
        self.ensure_one()
        return self.picking_id.with_context(is_confirm_wiz=True).button_validate()
