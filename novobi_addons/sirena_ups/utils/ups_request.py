# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.
# This file contains new customized function for omni_ups/models/ups_request/create_shipment_label()
# - [SRN-127] Change stock label size to 4" x 8"
import json
import requests

from odoo.addons.omni_ups.models.ups_request import UPSRequest


def new_create_shipment_label(self, shipper_number, package_detail, shipper, ship_from, ship_to, service_type,
                              insurance_detail=None, confirmation=None, shipping_info=None,
                              label_file_type='GIF', is_return=False, is_residential=False, references=[]):
    endpoint = self.restful_url + self.ship_restful
    headers = self._generate_header()

    weight_measurement = 'LBS'
    if service_type == '92':
        weight_measurement = 'OZS'

    send_packages = self.set_package_detail(package_detail, insurance_detail, True, confirmation, weight_measurement)

    # Bill Receiver 'Bill My Account'
    shipment_charge = dict()
    shipment_charge.update({"Type": "01"})
    if (shipping_info and shipping_info.get('shipment_options')
            and shipping_info['shipment_options'].get('change_billing')):
        change_billing = shipping_info['shipment_options']['change_billing']
        shipment_charge.update({
            'BillReceiver': {
                'AccountNumber': change_billing['account'],
                'Address': {
                    'PostalCode': change_billing['zipcode']
                }
            }
        })
    else:
        shipment_charge.update({
            'BillShipper': {
                'AccountNumber': shipper_number or '',
            }
        })
    payment_info = {
        "ShipmentCharge": shipment_charge
    }

    # Get the name of ship from as AttentionName if ship from is a contact of shipper
    if ship_from.parent_id.id == shipper.id:
        shipper_info = self._get_ship_partner_information(shipper,
                                                          AttentionName=ship_from.name,
                                                          Name=shipper.name)
    else:
        shipper_info = self._get_ship_partner_information(shipper)

    shipper_info.update({"ShipperNumber": shipper_number})

    contact_ship_to_info = {
        'Name': ship_to.parent_id.name or ship_to.company_name if ship_to.parent_id.is_company or ship_to.company_name else ship_to.name,
        'AttentionName': ship_to.name if ship_to.parent_id.is_company or ship_to.company_name else ''
    }

    if is_return:
        if ship_from.parent_id.id == shipper.id:
            contact_ship_to_info = {
                'Name': shipper.name,
                'AttentionName': ship_from.name
            }
        else:
            contact_ship_to_info = {
                'Name': ship_from.name,
            }
    ship_to_info = self._get_ship_partner_information(ship_to if not is_return else ship_from, **contact_ship_to_info)

    if is_residential:
        ship_to_info['Address'].update({
            'ResidentialAddressIndicator': ''
        })

    contact_ship_from_info = {}

    if is_return:
        contact_ship_from_info = {
            'Name': ship_to.parent_id.name or ship_to.company_name if ship_to.parent_id.is_company or ship_to.company_name else ship_to.name,
            'AttentionName': ship_to.name if ship_to.parent_id.is_company or ship_to.company_name else ''
        }

    ship_from_info = self._get_ship_partner_information(ship_from if not is_return else ship_to,
                                                        **contact_ship_from_info)

    request_data = {
        "ShipmentRequest": {
            "Shipment": {
                "Request": {
                    "SubVersion": self.sub_version
                },
                "Shipper": shipper_info,
                "ShipTo": ship_to_info,
                "ShipFrom": ship_from_info,
                "Service": {
                    "Code": service_type,
                    "Description": "Service Code"
                },
                "PaymentInformation": payment_info,
                "Package": send_packages,
                "ShipmentRatingOptions": {
                    "NegotiatedRatesIndicator": "1"

                }
            },
            "LabelSpecification": {
                "LabelImageFormat": {
                    "Code": label_file_type
                }
            },

        }
    }

    if references:
        ref_datas = [{
            'Value': ref['value'],
            'Code': ref['code']
        } for ref in references]
        for package in request_data['ShipmentRequest']['Shipment']['Package']:
            package.update({
                'ReferenceNumber': ref_datas
            })
    if shipping_info:
        request_data["ShipmentRequest"]["Shipment"] = self._create_shipment_other_options(
            shipment=request_data["ShipmentRequest"]["Shipment"],
            other_options=shipping_info,
            request_type='shipping',
            is_return=is_return
        )
    if label_file_type == 'ZPL':
        request_data["ShipmentRequest"]["LabelSpecification"].update({
            "LabelStockSize": {
                # [SRN-127] Change to 4" x 8" label stock size for UPS ZPL labels
                "Height": "8" if shipping_info.get('label_stock_type', '4X8') == '4X8' else "6",
                # [SRN-127]
                "Width": "4",
            }
        })

    result = {}
    try:
        self.debug_logger(json.dumps(request_data), 'ups_request_ship')
        response = requests.post(url=endpoint, data=json.dumps(request_data), headers=headers)
        self.debug_logger(response.content, 'ups_response_ship')

        if response.status_code == 200:
            shipment_res = response.json()['ShipmentResponse']['ShipmentResults']
            package_results = shipment_res['PackageResults']
            if isinstance(package_results, dict):
                package_results = [package_results]
            result['label_binary_data'] = {
                pr['TrackingNumber']: self.save_label(pr['ShippingLabel']['GraphicImage'],
                                                      label_file_type=label_file_type)
                for pr in package_results
            }
            result['tracking_ref'] = shipment_res['ShipmentIdentificationNumber']

            # Some users are qualified to receive negotiated rates
            negotiated_rate = 'NegotiatedRateCharges' in shipment_res and \
                              shipment_res['NegotiatedRateCharges']['TotalCharge']['MonetaryValue'] or None

            result['price'] = negotiated_rate or shipment_res['ShipmentCharges']['TotalCharges'][
                'MonetaryValue'] or ''
            result['price_without_discounts'] = 0.0
            if negotiated_rate:
                result['price_without_discounts'] = shipment_res['ShipmentCharges']['TotalCharges']['MonetaryValue']
            result['currency_code'] = shipment_res['ShipmentCharges']['TotalCharges']['CurrencyCode'] or ''

        elif response.status_code in [400, 401, 402, 403, 406, 422, 423, 429]:
            errors = self.parse_errors(response)
            if errors:
                result['errors'] = errors

    except IOError as e:
        result['errors'] = self.get_error_message('0', 'UPS Server Not Found:\n%s' % e)
    except Exception as e:
        result['errors'] = self.get_error_message('0', 'Server Error:\n%s' % e)
    return result


UPSRequest.create_shipment_label = new_create_shipment_label
