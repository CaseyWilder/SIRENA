from odoo import api, fields, models, _


class PayslipCompensation(models.Model):
    _inherit = 'payslip.compensation'

    # ===== Helper fields =====
    linked_pending_compensation_id = fields.Many2one('pending.compensation', string='Linked Pending Compensation')
