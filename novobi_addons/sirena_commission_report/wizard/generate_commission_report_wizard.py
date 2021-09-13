import logging
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class GenerateHolidaysWizard(models.TransientModel):
    _name = 'generate.commission.report.wizard'
    _description = 'Creates Commission Report'

    start_date = fields.Date('Start Date')
    end_date = fields.Date('End Date')
    is_amazon_report = fields.Boolean('Is Amazon Commission Report?')
    commission_lines = fields.Many2many('sale.order.line', string='Commission Lines')
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)

    def button_generate_commission_report(self):
        """
        Create Commission Report
        """
        self.ensure_one()
        if self.start_date > self.end_date:
            raise ValidationError('End Date must not be earlier than Start Date!')
        domain = self._get_commission_domain()
        commission_lines = self.env['sale.order.line'].search(domain)
        report = self.env['commission.report'].create({
            'start_date': self.start_date,
            'end_date': self.end_date,
            'is_amazon_report': self.is_amazon_report,
            'company_id': self.company_id.id,
            'commission_lines': commission_lines.ids
        })
        return {
            'type': 'ir.actions.act_window',
            'name': 'Commission Report',
            'view_mode': 'form',
            'res_model': 'commission.report',
            'res_id': report.id
        }

    def _get_commission_domain(self):
        """
        Get domain for commission lines
        :return: domain
        """
        return [('commission_user_id', '!=', False), ('company_id', '=', self.company_id.id),
                ('date_order', '>=', self.start_date), ('date_order', '<=', self.end_date),
                ('is_amazon_order_item', '=', self.is_amazon_report)]
