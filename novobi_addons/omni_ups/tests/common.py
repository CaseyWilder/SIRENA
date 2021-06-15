# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from odoo.addons.novobi_shipping_account.tests.common import CarrierTestCommon, tagged


@tagged('post_install', 'basic_test', '-at_install')
class UPSTestCommon(CarrierTestCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._add_shipping_account()

    @classmethod
    def _add_shipping_account(cls):
        shipping_account_1_data = {
            'name': 'UPS - Test - 1',
            'provider': 'ups',
            'ups_username': 'ups_unittest',
            'ups_passwd': 'UpStrOngP45s',
            'ups_shipper_number': 'TEST01',
            'ups_access_number': 'F488DA300C8EBC29',
            'handling_fee': '1.2',
        }
        cls.shared_data.update(shipping_account_1=shipping_account_1_data)
        cls.test_data.update(shipping_account_1=cls.env['shipping.account'].create(shipping_account_1_data))
