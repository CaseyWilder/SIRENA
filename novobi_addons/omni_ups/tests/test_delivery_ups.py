# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from unittest import mock
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import UserError

from .common import UPSTestCommon, tagged


@tagged('post_install', 'basic_test', '-at_install')
class TestDeliveryUPS(UPSTestCommon):

    def setUp(self):
        super().setUp()
        self._add_shipping_order()

    def _add_shipping_order(self):
        test_data = self.test_data
        shipping_account_1 = test_data['shipping_account_1']

        picking_1_data = {
            'shipping_account_id': shipping_account_1.id,
            'handling_fee': 0.4,
            'is_mul_packages': False,
            'delivery_carrier_id': shipping_account_1.delivery_carrier_ids.filtered(lambda d: d.ups_default_service_type == '02').id,
            'default_packaging_id': self.env.ref('delivery_ups.ups_packaging_02').id,
            'partner_id': test_data['shipping_address_us_1'].id,
            'location_id': self.env.ref('stock.stock_location_stock').id,
            'location_dest_id': self.env.ref('stock.stock_location_customers').id,
            'picking_type_id': self.env.ref('stock.picking_type_out').id,
            'package_shipping_weight': 3.2,
            'shipping_date': fields.Date.today(),
        }
        self.shared_data.update(picking_1=picking_1_data)
        self.picking_1 = self.env['stock.picking'].create(picking_1_data)

    def set_up_environment(self):
        test_data = self.test_data
        self._set_up_environment(
            user=test_data['admin_user'],
            company=test_data['company_1'],
        )

    def test_check_connection(self):
        shared_data = self.shared_data
        test_data = self.test_data
        sa1 = test_data['shipping_account_1']
        sa1d = shared_data['shipping_account_1']
        cases = ('passed', 'failed')
        error_msg = 'This connection test is failed!'
        test_cases = {
            cases[0]: (dict(), False),
            cases[1]: (dict(errors=dict(error_message=error_msg)), error_msg),
        }

        for case in cases:
            with self.subTest(case=case):
                with patch('odoo.addons.omni_ups.models.ups_request.UPSRequest.__init__', autospec=True, return_value=None) as mock_request_init:
                    with patch('odoo.addons.omni_ups.models.ups_request.UPSRequest.get_shipping_rate_and_delivery_time', autospec=True) as mock_get:
                        mock_get.return_value = test_cases[case][0]

                        result = self.env['delivery.carrier'].ups_check_connection(sa1)

                        mock_request_init.assert_called_once_with(
                            mock.ANY,
                            debug_logger=mock.ANY,
                            username=sa1d['ups_username'],
                            password=sa1d['ups_passwd'],
                            access_number=sa1d['ups_access_number'],
                            prod_environment=mock.ANY,
                        )
                        mock_get.assert_called_once()
                        self.assertEqual(result.get('error_message', 'unknown'), test_cases[case][1])

    def test_create_shipping_label_no_return_error(self):
        shared_data = self.shared_data
        sa1d = shared_data['shipping_account_1']
        error_msg = 'Delivery Request Rejected!'
        cases = {
            'No response': dict(),
            'Error in response': dict(errors=[dict(error_message=error_msg)]),
        }

        for case, response in cases.items():
            with self.subTest(case):
                with patch('odoo.addons.omni_ups.models.ups_request.UPSRequest.__init__', autospec=True, return_value=None) as mock_request_init:
                    with patch('odoo.addons.omni_ups.models.ups_request.UPSRequest.create_shipment_label',
                               autospec=True, return_value=response) as mock_create_label:
                        with patch('odoo.addons.omni_ups.models.ups_request.UPSRequest.get_time_in_transit', autospec=True) as mock_get_time:
                            with self.assertRaises(UserError):
                                self.picking_1.action_create_label()

                            mock_request_init.assert_called_once_with(
                                mock.ANY,
                                debug_logger=mock.ANY,
                                username=sa1d['ups_username'],
                                password=sa1d['ups_passwd'],
                                access_number=sa1d['ups_access_number'],
                                prod_environment=mock.ANY,
                            )

                            mock_create_label.assert_called_once()
                            mock_get_time.assert_not_called()

    @patch('odoo.tools.pdf.merge_pdf', autospec=True)
    def test_create_shipping_label_no_return(self, mock_merge_pdf):
        def merge_bin(bins):
            return b''.join(bins)

        shared_data = self.shared_data
        sa1d = shared_data['shipping_account_1']
        ups_label_res = {
            'label_binary_data': {
                '1Z73Y37V0197037139': b'ThisIsOnlyATest',
            },
            'tracking_ref': '1Z73Y37V0197037139',
            'price': '12.27',
            'price_without_discounts': 0.0,
            'currency_code': 'USD',
        }
        ups_time_res = {
            'estimated_date': '2018-05-24'
        }
        cases = {
            'Standard': (ups_label_res, ups_time_res, 12.67, '05/24/2018'),
            'Missing Time': (ups_label_res, dict(), 12.67, 'N/A'),
            'Error Time': (ups_label_res, dict(errors=['Delivery Time Request Rejected!']), 12.67, 'N/A'),
        }
        mock_merge_pdf.side_effect = merge_bin

        for case, (ship_res, time_res, est_price, est_date) in cases.items():
            with self.subTest(case):
                with patch('odoo.addons.omni_ups.models.ups_request.UPSRequest.__init__', autospec=True, return_value=None) as mock_request_init:
                    with patch('odoo.addons.omni_ups.models.ups_request.UPSRequest.create_shipment_label',
                               autospec=True, return_value=ship_res) as mock_create_label:
                        with patch('odoo.addons.omni_ups.models.ups_request.UPSRequest.get_time_in_transit',
                                   autospec=True, return_value=time_res) as mock_get_time:
                            self.picking_1.action_create_label()

                            mock_request_init.assert_called_once_with(
                                mock.ANY,
                                debug_logger=mock.ANY,
                                username=sa1d['ups_username'],
                                password=sa1d['ups_passwd'],
                                access_number=sa1d['ups_access_number'],
                                prod_environment=mock.ANY,
                            )

                            mock_create_label.assert_called_once()
                            mock_get_time.assert_called_once()

                            self.assertRecordValues(self.picking_1, [{
                                'is_create_label': True,
                                'shipping_cost': est_price,
                                'shipping_cost_without_discounts': ups_label_res['price_without_discounts'],
                                'shipping_estimated_date': est_date,
                                'carrier_tracking_ref': ups_label_res['tracking_ref'],
                            }])

    def test_get_carrier_rate(self):
        shared_data = self.shared_data
        sa1d = shared_data['shipping_account_1']
        error_msg = 'Delivery Rate and Time Rejected!'
        cases = {
            'No response': (dict(), dict(success=False, error_message=mock.ANY)),
            'Error in response': (dict(errors=[dict(error_message=error_msg)]), {
                'success': False,
                'price': 0.0,
                'price_without_discounts': 0.0,
                'estimated_date': 'N/A',
                'error_message': mock.ANY,
                'warning_message': False
            }),
            'Standard': ({
                'currency_code': 'USD',
                'price': 41.21,
                'price_without_discounts': 0.0,
                'estimated_date': '20180815',
            }, {
                'success': True,
                'price': 41.61,
                'price_without_discounts': 0.0,
                'estimated_date': '2018-08-15',
                'error_message': False,
                'warning_message': False
            }),
            'Missing Date': ({
                'currency_code': 'USD',
                'price': 12.79,
                'price_without_discounts': 1.43,
                'estimated_date': None,
            }, {
                'success': True,
                'price': 13.19,
                'price_without_discounts': 1.83,
                'estimated_date': 'N/A',
                'error_message': False,
                'warning_message': False
            })
        }

        for case, (get_res, expected) in cases.items():
            with self.subTest(case):
                with patch('odoo.addons.omni_ups.models.ups_request.UPSRequest.__init__', autospec=True, return_value=None) as mock_request_init:
                    with patch('odoo.addons.omni_ups.models.ups_request.UPSRequest.get_shipping_rate_and_delivery_time',
                               autospec=True, return_value=get_res) as mock_get:
                        res = self.picking_1.get_carrier_rate()

                        mock_request_init.assert_called_once_with(
                            mock.ANY,
                            debug_logger=mock.ANY,
                            username=sa1d['ups_username'],
                            password=sa1d['ups_passwd'],
                            access_number=sa1d['ups_access_number'],
                            prod_environment=mock.ANY,
                        )

                        mock_get.assert_called_once()
                        self.assertDictEqual(res, expected)

    @patch('odoo.addons.omni_ups.models.ups_request.UPSRequest.void_label', autospec=True, return_value=dict(error_message='Error!'))
    @patch('odoo.addons.omni_ups.models.ups_request.UPSRequest.__init__', autospec=True, return_value=None)
    def test_void_label_error(self, mock_request_init, mock_void_label):
        shared_data = self.shared_data
        sa1d = shared_data['shipping_account_1']
        self.picking_1.update({
            'is_create_label': True,
            'carrier_tracking_ref': '1Z73Y37V0197037139',
        })

        with self.assertRaises(UserError):
            self.picking_1.button_void_label()

        mock_request_init.assert_called_once_with(
            mock.ANY,
            debug_logger=mock.ANY,
            username=sa1d['ups_username'],
            password=sa1d['ups_passwd'],
            access_number=sa1d['ups_access_number'],
            prod_environment=mock.ANY,
        )
        mock_void_label.assert_called_once()

    @patch('odoo.addons.omni_ups.models.ups_request.UPSRequest.void_label', autospec=True, return_value=dict())
    @patch('odoo.addons.omni_ups.models.ups_request.UPSRequest.__init__', autospec=True, return_value=None)
    def test_void_label(self, mock_request_init, mock_void_label):
        shared_data = self.shared_data
        sa1d = shared_data['shipping_account_1']
        self.picking_1.update({
            'is_create_label': True,
            'carrier_tracking_ref': '1Z73Y37V0197037139',
        })

        try:
            self.picking_1.button_void_label()
        except UserError:
            self.fail('Void Label must pass without raising error!')

        mock_request_init.assert_called_once_with(
            mock.ANY,
            debug_logger=mock.ANY,
            username=sa1d['ups_username'],
            password=sa1d['ups_passwd'],
            access_number=sa1d['ups_access_number'],
            prod_environment=mock.ANY,
        )
        mock_void_label.assert_called_once()
        self.assertRecordValues(self.picking_1, [{
            'is_create_label': False,
            'carrier_tracking_ref': False,
        }])
