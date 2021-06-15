# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from functools import partial
from unittest.mock import patch, MagicMock

from odoo import fields

from odoo.addons.novobi_shipping_account.tests.utils import load_json

from .common import UPSTestCommon, tagged
from ..models.ups_request import UPSRequest


@tagged('post_install', 'basic_test', '-at_install')
class TestUPSRequest(UPSTestCommon):

    def setUp(self):
        super().setUp()
        self._add_requests()

    def _add_requests(self):
        def void_logger(_x, _y):
            return None

        shared_data = self.shared_data
        sa1d = shared_data['shipping_account_1']
        self.r1 = UPSRequest(void_logger, sa1d['ups_username'], sa1d['ups_passwd'], sa1d['ups_access_number'], False)

    @patch('odoo.addons.omni_ups.models.ups_request.requests.post', autospec=True)
    def test_get_time_in_transit(self, mock_post):
        test_data = self.test_data
        company_1 = test_data['company_1']
        shipping_address_us_1 = test_data['shipping_address_us_1']
        ship_datetime = {
            'date': fields.Date.today().strftime('%Y-%m-%d'),
            'time': '12:00:00',
        }
        mock_res = MagicMock(content=None, status_code=200,
                             json=partial(load_json, __file__, 'data/ups_get_time_in_transit.json'))
        mock_post.return_value = mock_res
        res = self.r1.get_time_in_transit(
            weight=0.1,
            service_type='02',
            ship_from=company_1,
            ship_to=shipping_address_us_1,
            ship_datetime=ship_datetime,
        )
        mock_post.assert_called_once()
        self.assertIsInstance(res, dict)

    @patch('odoo.addons.omni_ups.models.ups_request.requests.post', autospec=True)
    def test_get_shipping_rate_and_delivery_time(self, mock_post):
        test_data = self.test_data
        shared_data = self.shared_data
        sa1d = shared_data['shipping_account_1']
        company_1 = test_data['company_1']
        shipping_address_us_1 = test_data['shipping_address_us_1']
        ship_datetime = {
            'date': fields.Date.today().strftime('%Y-%m-%d'),
            'time': '12:00:00',
        }
        package_detail = [{'packaging': '02', 'length': 1, 'width': 2, 'height': 3, 'weight': 0.5}]
        mock_res = MagicMock(content=None, status_code=200,
                             json=partial(load_json, __file__, 'data/ups_get_shipping_rate_and_delivery_time.json'))
        mock_post.return_value = mock_res

        res = self.r1.get_shipping_rate_and_delivery_time(
            shipment_info=False,
            package_detail=package_detail,
            shipper=company_1,
            ship_from=company_1,
            ship_to=shipping_address_us_1,
            service_type='02',
            ship_datetime=ship_datetime,
            insurance_detail=False,
            shipper_number=sa1d['ups_shipper_number'],
        )
        mock_post.assert_called_once()
        self.assertIsInstance(res, dict)

    @patch('odoo.addons.omni_ups.models.ups_request.requests.post', autospec=True)
    def test_create_shipment_label(self, mock_post):
        test_data = self.test_data
        shared_data = self.shared_data
        sa1d = shared_data['shipping_account_1']
        package_detail = [{'packaging': '02', 'length': 1, 'width': 2, 'height': 3, 'weight': 0.5}]
        company_1 = test_data['company_1']
        shipping_address_us_1 = test_data['shipping_address_us_1']
        mock_res = MagicMock(content=None, status_code=200,
                             json=partial(load_json, __file__, 'data/ups_create_shipment_label.json'))
        mock_post.return_value = mock_res
        res = self.r1.create_shipment_label(
            shipper_number=sa1d['ups_shipper_number'],
            package_detail=package_detail,
            shipper=company_1,
            ship_from=company_1,
            ship_to=shipping_address_us_1,
            service_type='02',
            label_file_type='ZPL',
        )
        mock_post.assert_called_once()
        self.assertIsInstance(res, dict)

    @patch('odoo.addons.omni_ups.models.ups_request.requests.delete', autospec=True)
    def test_void_label(self, mock_delete):
        shipment_id = '1ZISDE016691676846'
        mock_res = MagicMock(content=None, status_code=200,
                             json=partial(load_json, __file__, 'data/ups_void_label.json'))
        mock_delete.return_value = mock_res
        res = self.r1.void_label(shipment_id)
        mock_delete.assert_called_once()
        self.assertIsInstance(res, dict)
