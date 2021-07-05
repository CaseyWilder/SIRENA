from odoo import fields, models, api, _
from odoo.exceptions import ValidationError

from ..utils.utils import is_valid_routing_number


class ResPartnerBank(models.Model):
    _inherit = 'res.partner.bank'

    aba_routing = fields.Char(string="ABA/Routing", help="American Bankers Association Routing Number")

    @api.constrains('aba_routing')
    def _check_aba_routing(self):
        for bank in self:
            if not is_valid_routing_number(bank.aba_routing):
                raise ValidationError(_('ABA/Routing is invalid.'))


class ResBank(models.Model):
    _inherit = 'res.bank'

    immediate_org = fields.Char('Immediate Origin', help='Using for ACH header')
