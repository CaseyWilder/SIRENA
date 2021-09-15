from odoo import models, fields, api, _
from odoo.exceptions import UserError


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    commission_user_id = fields.Many2one('res.partner', string='Commission Salesperson', store=True, compute='_compute_commission_amount')
    commission_amount = fields.Float(string='Commission Amount', store=True, compute='_compute_commission_amount')
    commission_state = fields.Selection([('new', 'New'), ('draft', 'Draft'), ('posted', 'Posted'), ('cancel', 'Cancelled')],
                                        compute='_compute_commission_state', store=True)
    commission_payment = fields.Many2one('account.payment', 'Commission Payment', copy=False)

    @api.depends('order_id.state')
    def _compute_commission_amount(self):
        CommissionList = self.sudo().env['commission.list']
        self.filtered(lambda x: x.order_id.state == 'cancel').write({
            'commission_user_id': False,
            'commission_amount': False
        })
        for rec in self.filtered(lambda x: x.order_id.state == 'sale'):
            commission = CommissionList.search([('product_id','=', rec.product_id.id), ('partner_id','=',rec.order_partner_id.id)], limit=1)
            if commission:
                rec.commission_user_id = commission.user_id
                rec.commission_amount = commission.commission_amount

    @api.depends('commission_payment', 'commission_payment.state')
    def _compute_commission_state(self):
        for record in self:
            record.commission_state = 'new' if not record.commission_payment else record.commission_payment.state

    def action_create_commission_payment(self):
        payment_env = self.env['account.payment'].sudo()
        check_method = self.env.ref('account_check_printing.account_payment_method_check')

        if not check_method:
            raise UserError(_('No payment method "Check" is found!'))

        for record in self.filtered(lambda r: not r.commission_payment and r.commission_amount):
            journal_id = record.company_id.commission_amazon_journal_id if record.is_amazon_order_item else\
                record.company_id.commission_journal_id

            if not journal_id:
                raise UserError(_('Please make sure the bank journal for commission report has been set in Sales > Configuration > Settings and try again.'))

            record.commission_payment = payment_env.create({
                'payment_type': 'outbound',
                'partner_type': 'supplier',
                'partner_id': record.commission_user_id.id,
                'amount': record.commission_amount,
                'payment_method_id': check_method.id,
                'journal_id': journal_id.id,
                'commission_line_id': record.id,
            })

    def action_view_commission_payment(self):
        payments = self.mapped('commission_payment')

        if not payments:
            return

        action = self.env['ir.actions.actions']._for_xml_id('account.action_account_payments_payable')

        if len(payments) > 1:
            action['domain'] = [('id', 'in', payments.ids)]
        else:
            form_view = [(self.env.ref('account.view_account_payment_form').id, 'form')]
            if 'views' in action:
                action['views'] = form_view + [(state, view) for state, view in action['views'] if view != 'form']
            else:
                action['views'] = form_view
            action['res_id'] = payments.id

        return action


