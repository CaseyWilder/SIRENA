# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class PaymentDeposit(models.Model):
    _inherit = 'account.payment'

    property_account_customer_deposit_id = fields.Many2one('account.account', company_dependent=True, copy=True,
                                                           string='Customer Deposit Account',
                                                           domain=lambda self: [('user_type_id', 'in', [self.env.ref('account.data_account_type_current_liabilities').id]),
                                                                                ('deprecated', '=', False), ('reconcile', '=', True)])
    property_account_vendor_deposit_id = fields.Many2one('account.account', company_dependent=True, copy=True,
                                                         string='Vendor Deposit Account',
                                                         domain=lambda self: [('user_type_id', 'in', [self.env.ref('account.data_account_type_prepayments').id]),
                                                                              ('deprecated', '=', False), ('reconcile', '=', True)])
    deposit_ids = fields.Many2many('account.move', string='Deposit Entries')
    sale_deposit_id = fields.Many2one('sale.order', 'Sales Order',
                                      help='Is this deposit made for a particular Sale Order?')
    purchase_deposit_id = fields.Many2one('purchase.order', 'Purchase Order',
                                          help='Is this deposit made for a particular Purchase Order?')

    # -------------------------------------------------------------------------
    # ONCHANGE METHODS
    # -------------------------------------------------------------------------
    @api.onchange('partner_id')
    def _update_default_deposit_account(self):
        """
        Change deposit account like deposit account of partner
        """
        if self.partner_id and self.is_deposit:
            if self.partner_id.property_account_customer_deposit_id and self.partner_type == 'customer':
                self.property_account_customer_deposit_id = self.partner_id.property_account_customer_deposit_id.id
            elif self.partner_id.property_account_vendor_deposit_id and self.partner_type == 'supplier':
                self.property_account_vendor_deposit_id = self.partner_id.property_account_vendor_deposit_id.id

    # -------------------------------------------------------------------------
    # BUSINESS METHODS
    # -------------------------------------------------------------------------
    def action_post(self):
        """
        Override
        Check if total amount of deposits of an order has exceeded amount of this order
        """
        for record in self:
            if record.partner_type == 'customer':
                order = record.sale_deposit_id
                msg = 'Total deposit amount cannot exceed sales order amount'
            else:
                order = record.purchase_deposit_id
                msg = 'Total deposit amount cannot exceed purchase order amount'
            if order:
                deposit_total = record.amount_total_signed
                # Convert total deposit to currency of SO if needed
                currency_date = record.partner_type == 'customer' and order.date_order or order.date_approve
                if self.env.company.currency_id != order.currency_id:
                    deposit_total = self.env.company.currency_id._convert(
                        deposit_total,
                        order.currency_id,
                        self.env.company,
                        currency_date or fields.Date.today()
                    )
                if deposit_total > order.remaining_total:
                    raise ValidationError(_(msg))

        return super(PaymentDeposit, self).action_post()

    def action_draft(self):
        """
        Override
        Cancel, remove deposit from invoice and delete deposit moves
        """
        super(PaymentDeposit, self).action_draft()
        moves = self.mapped('deposit_ids')
        moves.filtered(lambda move: move.state == 'posted').button_draft()
        moves.with_context(force_delete=True).unlink()

    # -------------------------------------------------------------------------
    # HELPERS
    # -------------------------------------------------------------------------
    def _onchange_partner_order_id(self, order_field, state):
        """
        Helper method: Get the domain of order field on deposit form according to partner
        """
        if self.partner_id:
            partner_id = self.partner_id.commercial_partner_id.id
            if self[order_field] and self[order_field].partner_id.commercial_partner_id.id != partner_id:
                self[order_field] = False
            return {
                'domain': {
                    order_field: [('partner_id.commercial_partner_id', '=', partner_id), ('state', 'in', state)]
                }
            }
        else:
            self[order_field] = False

    def _validate_order_id(self, order_field, model_name):
        """
        Helper method: Check if commercial partner of deposit is the same as the one of payment
        """
        for payment in self:
            partner_id = payment.partner_id.commercial_partner_id.id
            if payment[order_field] and payment[order_field].partner_id.commercial_partner_id.id != partner_id:
                raise ValidationError(_("The {}'s customer does not match with the deposit's.".format(model_name)))
