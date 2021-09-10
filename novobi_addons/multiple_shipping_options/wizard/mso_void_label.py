from odoo import api, fields, models, _
from odoo.exceptions import UserError


class MsoVoidLabel(models.TransientModel):
    _name = 'mso.void.label'

    picking_id = fields.Many2one('stock.picking')
    label_status = fields.Selection(related='picking_id.label_status')

    is_void_first_label = fields.Boolean(string='Option 1')
    is_void_second_label = fields.Boolean(string='Option 2')

    def mso_action_confirm(self):
        if not self.picking_id:
            return

        if not self.is_void_first_label and not self.is_void_second_label:
            raise UserError('Please select at least 1 option!')

        if self.is_void_first_label:
            if self.label_status in ['1', '3']:
                self.picking_id.is_void_first_label = True
            else:
                raise UserError('No shipping label to void for Option 1!')
        else:
            self.picking_id.is_void_first_label = False

        if self.is_void_second_label:
            if self.label_status in ['2', '3']:
                self.picking_id.is_void_second_label = True
            else:
                raise UserError('No shipping label to void for Option 2!')
        else:
            self.picking_id.is_void_second_label = False

        self.picking_id.button_void_label()
