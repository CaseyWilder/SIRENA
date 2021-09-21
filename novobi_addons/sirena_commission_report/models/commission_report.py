from odoo import models, fields, api, _
from odoo.exceptions import UserError


class CommissionList(models.Model):
    _name = 'commission.report'
    _description = 'Commission Report'

    name = fields.Char(string='Name', compute='_compute_name')
    start_date = fields.Date('Start Date')
    end_date = fields.Date('End Date')
    is_amazon_report = fields.Boolean('Is Amazon Commission Report?')
    company_id = fields.Many2one('res.company', string='Company')
    commission_lines = fields.Many2many('sale.order.line', string='Commission Lines')

    number_payments = fields.Integer('Number of check payments', compute='_compute_number_payments')
    total_amount = fields.Float('Total Amount', compute='_compute_total_amount', store=True)

    @api.depends('start_date','end_date')
    def _compute_name(self):
        for rec in self:
            rec.name = '%s (%s - %s)' % ('Amazon' if rec.is_amazon_report else 'Sales', rec.start_date, rec.end_date)

    def _compute_number_payments(self):
        for record in self:
            record.number_payments = len(record.commission_lines.mapped('commission_payment'))

    @api.depends('commission_lines', 'commission_lines.commission_amount')
    def _compute_total_amount(self):
        for record in self:
            record.total_amount = sum(record.commission_lines.mapped('commission_amount'))

    def action_create_commission_payments(self):
        self.ensure_one()
        payment_env = self.env['account.payment'].sudo()
        check_method = self.env.ref('account_check_printing.account_payment_method_check')

        if not check_method:
            raise UserError(_('No payment method "Check" is found!'))
        journal_id = self.company_id.commission_amazon_journal_id if self.is_amazon_report else \
            self.company_id.commission_journal_id
        if not journal_id:
            raise UserError(_(
                'Please make sure the bank journal for commission report has been set in Sales > Configuration > Settings and try again.'))
        if not self.commission_lines:
            return
        commission_line_ids = tuple(self.commission_lines.ids) if len(self.commission_lines) > 1 \
            else "(%s)" % str(self.commission_lines.id)

        sql_query = """
            SELECT      sol.commission_user_id as commission_user_id,
                        sum(sol.commission_amount) as total_amount                    
            FROM        sale_order_line sol
            WHERE       sol.commission_user_id is not null
                and     sol.company_id = %s
                and     sol.is_amazon_order_item is FALSE 
                and     sol.commission_payment is null
                and     sol.id in %s
            GROUP BY    sol.commission_user_id
        """ % (str(self.company_id.id), commission_line_ids)
        self._cr.execute(sql_query)
        full_data = self._cr.dictfetchall()
        for data in full_data:
            batch_lines = self.commission_lines.filtered(lambda line: line.commission_user_id.id == data['commission_user_id'] and not line.commission_payment)
            if batch_lines:
                batch_lines.commission_payment = payment_env.create({
                    'payment_type': 'outbound',
                    'partner_type': 'supplier',
                    'partner_id': data['commission_user_id'],
                    'amount': data['total_amount'],
                    'payment_method_id': check_method.id,
                    'journal_id': journal_id.id,
                    'commission_line_ids': batch_lines.ids,
                    'currency_id': batch_lines[0].currency_id.id,
                })

    def action_view_commission_payments(self):
        self.ensure_one()
        return self.commission_lines.action_view_commission_payment()
