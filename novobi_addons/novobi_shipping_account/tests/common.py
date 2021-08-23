# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from odoo import models
from odoo.tests.common import SingleTransactionCase, tagged


@tagged('post_install', 'basic_test', '-at_install')
class CarrierTestCommon(SingleTransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Share data contains data for creating testing data which is used across multiple classes
        cls.shared_data = dict()
        # Test data contains master testing data for testing, of course!
        # It should contains only data can be reused. Transaction data should not be included here.
        # These data is not immutable and may change during the tests.
        # But significant changes are not allowed
        cls.test_data = dict()

        cls._add_users()
        cls._add_customers()
        cls._add_companies()
        cls._add_warehouses()
        cls._add_operation_types()

    def setUp(self):
        super().setUp()
        self.set_up_environment()

    @classmethod
    def _add_users(cls):
        res_users_model = cls.env['res.users']

        # Admin
        admin_user = res_users_model.create({
            'name': 'Boss!',
            'login': 'boss',
            'password': 'boss',
            'groups_id': [
                (5, 0, 0),
                (4, cls.env.ref('base.group_user').id),
                (4, cls.env.ref('sales_team.group_sale_manager').id),
                (4, cls.env.ref('account.group_account_manager').id),
                (4, cls.env.ref('stock.group_stock_manager').id),
                (4, cls.env.ref('base.group_erp_manager').id),
                (4, cls.env.ref('base.group_system').id),
            ],
        })
        admin_user.partner_id.email = 'boss@test.com'

        cls.test_data.update({
            'admin_user': admin_user,
        })

    @classmethod
    def _add_companies(cls):
        res_company_model = cls.env['res.company']

        company_1 = res_company_model.create({
            'name': 'Test Company 1',
            'phone': '+1 512-897-3977',
            'email': 'testing1.company@auto-test.test',
            'street': '1447 Brentwood Drive',
            'street2': 'Suite 555',
            'city': 'Austin',
            'state_id': cls.env.ref('base.state_us_44').id,  # Texas
            'country_id': cls.env.ref('base.us').id,  # USA
            'zip': '78701',
            'website': 'https://testing1-company.auto-test.test',
            'currency_id': cls.env.ref('base.USD').id,
        })

        cls.test_data.update({
            'company_1': company_1,
        })

    @classmethod
    def _add_warehouses(cls):
        stock_warehouse_model = cls.env['stock.warehouse']

        company_1_warehouse_1 = stock_warehouse_model.search([
            ('company_id', '=', cls.test_data['company_1'].id)
        ], order='id asc', limit=1)

        cls.test_data.update({
            'company_1_warehouse_1': company_1_warehouse_1,
        })

    @classmethod
    def _add_operation_types(cls):
        test_data = cls.test_data
        stock_picking_type_model = cls.env['stock.picking.type']

        company_1_warehouse_1_out_1 = stock_picking_type_model.create({
            'name': 'Test Out 1',
            'company_id': test_data['company_1'].id,
            'code': 'outgoing',
            'warehouse_id': test_data['company_1_warehouse_1'].id,
            'sequence_code': 'OUT',
        })

        test_data.update({
            'company_1_warehouse_1_out_1': company_1_warehouse_1_out_1,
        })

    @classmethod
    def _add_customers(cls):
        res_partner_model = cls.env['res.partner']

        # Contacts
        # Partner with the same main and sub-contacts
        partner_us_1_data = {
            'name': 'Heather A Flynn',
            'phone': '+1 917-248-2381',
            'email': 'heather.flynn@auto-test.test',
            'street': '3251 Francis Mine',
            'street2': 'Apt 211',
            'city': 'Huletts Landing',
            'state_id': cls.env.ref('base.state_us_27').id,  # New York
            'country_id': cls.env.ref('base.us').id,  # USA
            'zip': '12841',
        }
        main_contact_us_1 = res_partner_model.create({**partner_us_1_data, **{
            'type': 'contact',
            'customer_rank': 1,
        }})
        billing_address_us_1 = res_partner_model.create({**partner_us_1_data, **{
            'type': 'invoice',
            'parent_id': main_contact_us_1.id,
        }})
        shipping_address_us_1 = res_partner_model.create({**partner_us_1_data, **{
            'type': 'delivery',
            'parent_id': main_contact_us_1.id,
        }})

        # Partner with different main and sub-contacts
        partner_us_2_data_1 = {
            'name': 'Matthew T Domino',
            'phone': '+1 415-877-3664',
            'email': 'matthew.domino@auto-test.test',
            'street': '3914 Roosevelt Street',
            'street2': 'PO. Box 5441',
            'city': 'Mill Valley',
            'state_id': cls.env.ref('base.state_us_5').id,  # California
            'country_id': cls.env.ref('base.us').id,  # USA
            'zip': '94941',
        }
        partner_us_2_data_2 = {
            'name': 'Lillian D Thompson',
            'phone': '+1 509-378-3903',
            'email': 'lillian.thompson@auto-test.test',
            'street': '1756 Goodwin Avenue',
            'street2': 'R24',
            'city': 'Spokane Valley',
            'state_id': cls.env.ref('base.state_us_48').id,  # Washington
            'country_id': cls.env.ref('base.us').id,  # USA
            'zip': '99206',
        }
        main_contact_us_2 = res_partner_model.create({**partner_us_2_data_1, **{
            'type': 'contact',
            'customer_rank': 1,
        }})
        billing_address_us_2 = res_partner_model.create({**partner_us_2_data_1, **{
            'type': 'invoice',
            'parent_id': main_contact_us_2.id,
        }})
        shipping_address_us_2 = res_partner_model.create({**partner_us_2_data_2, **{
            'type': 'delivery',
            'parent_id': main_contact_us_2.id,
        }})

        cls.shared_data.update({
            'partner_us_1_data': partner_us_1_data,
            'partner_us_2_data_1': partner_us_2_data_1,
            'partner_us_2_data_2': partner_us_2_data_2,
        })
        cls.test_data.update({
            'main_contact_us_1': main_contact_us_1,
            'billing_address_us_1': billing_address_us_1,
            'shipping_address_us_1': shipping_address_us_1,
            'main_contact_us_2': main_contact_us_2,
            'billing_address_us_2': billing_address_us_2,
            'shipping_address_us_2': shipping_address_us_2,
        })

    def _set_up_environment(self, user: models.Model, company: models.Model):
        # Shadow the current environment/cursor with the specified user.
        self.env = self.env(user=user)
        self.cr = self.env.cr
        user.company_ids |= company
        user.company_id = company

    def set_up_environment(self):
        """
        This method is meant to be inherited and overwritten.
        Here derived class can set up environment like user and company before running tests.
        """
