# -*- coding: utf-8 -*-
from odoo import api, models, fields, _


class ResCompany(models.Model):
    _inherit = 'res.company'

    @api.model
    def set_stock_valuation_accounts(self):
        """
        This function runs when we first install the module or load a new COA:
        create/set stock valuation accounts for existing locations.
        """
        def _create_account(self, account_key, company):
            info = account_info[account_key]

            account_id = self.env['account.account'].sudo().search([('code', 'like', info['code']),
                                                                    ('name', 'like', info['name']),
                                                                    ('user_type_id', '=', info['user_type_id']),
                                                                    ('company_id', '=', company.id)], limit=1)
            if not account_id:
                account_id = self.env['account.account'].sudo().create({
                    'code': info['code'] + '_default',
                    'name': info['name'],
                    'user_type_id': info['user_type_id'],
                    'company_id': company.id
                })

            return account_id

        def _assign_account(self, account_key, usage, company, scrap = False):
            location = self.env['stock.location'].search([('usage', '=', usage),
                                                          ('scrap_location', '=', scrap),
                                                          ('valuation_in_account_id', '=', False),
                                                          ('company_id', '=', company.id)])
            account = _create_account(self, account_key, company)
            location.write({'valuation_in_account_id': account.id,
                            'valuation_out_account_id': account.id})

        superself = self.sudo()
        all_companies = superself.search([])

        account_info = {
            'WIP': {'code': '1300',
                    'name': 'Work in Process',
                    'user_type_id': self.env.ref('account.data_account_type_current_assets').id},
            'INV': {'code': '5500',
                    'name': 'Inventory Adjustments',
                    'user_type_id': self.env.ref('account.data_account_type_direct_costs').id},
            'SCR': {'code': '5200',
                    'name': 'Scrap',
                    'user_type_id': self.env.ref('account.data_account_type_direct_costs').id}
        }

        for company in all_companies:
            if company.chart_template_id:
                _assign_account(self, 'WIP', 'production', company)
                _assign_account(self, 'INV', 'inventory', company)
                _assign_account(self, 'SCR', 'inventory', company, scrap=True)
