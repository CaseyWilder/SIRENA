from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from ..utils.utils import is_valid_routing_number


class DirectPaymentAccount(models.Model):
    _name = 'account.payment.direct'
    _description = 'Payment accounts for Direct Deposit'
    _order = 'sequence, id'

    currency_id = fields.Many2one('res.currency', related='employee_id.company_id.currency_id', readonly=True)
    sequence = fields.Integer('Sequence', default=10)
    employee_id = fields.Many2one('hr.employee', 'Employee', auto_join=True, required=True, ondelete='cascade')

    account_name = fields.Char('Account Name', help='Displayed on the employee paystub to represent the employee bank account.')
    routing_number = fields.Char('Routing Number', required=1)
    account_number = fields.Char('Account Number', required=1)
    account_type = fields.Selection([('checking', 'Checking'), ('saving', 'Savings')], required=True, default='checking')
    split_paychecks_type = fields.Selection(related='employee_id.split_paychecks_type')
    amount_fixed = fields.Monetary('Fixed Amount', default=0, required=True)
    amount_percentage = fields.Float('Percentage', digits=(16, 2), default=0, required=True)

    # Monetary/Float fields must contain positive value
    _sql_constraints = [
        ('positive_direct_amount_fixed',        'CHECK (amount_fixed >= 0)',        _('Fixed Amount must be positive.')),
        ('positive_direct_amount_percentage',   'CHECK (amount_percentage >= 0)',   _('Percentage must be positive.')),
    ]

    @api.model
    def default_get(self, fields):
        """
        If split_paychecks_type = percentage, compute the default amount of the next line.
        :param fields
        :return:
        """
        rec = super(DirectPaymentAccount, self).default_get(fields)
        ctx = self._context
        if not(ctx.get('split_paychecks_type', False) == 'percentage' and 'payment_account_ids' in ctx):
            return rec

        employee_id = self.employee_id.new({
            'payment_account_ids': self._context.get('payment_account_ids', [])
        })
        percentage = sum(employee_id.payment_account_ids.mapped('amount_percentage'))
        rec.update({'amount_percentage': max(100 - percentage, 0)})

        return rec

    @api.constrains('routing_number')
    def _check_routing_number(self):
        for record in self:
            if not is_valid_routing_number(record.routing_number):
                raise ValidationError(_('Routing Number of "{}" is invalid.'.format(record.account_name)))
