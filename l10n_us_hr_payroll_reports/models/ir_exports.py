from odoo import models, fields


class IrExportsLine(models.Model):
    _inherit = 'ir.exports.line'
    _order = 'sequence, id'

    sequence = fields.Integer('Sequence', default=10)
