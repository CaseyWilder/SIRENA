# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

import requests
import json
from odoo.addons.delivery_ups.models.ups_request import UPSRequest as UPSRequestBase, UPS_ERROR_MAP

SERVICE_LEVEL = {
    '03': 'GND',
    '11': 'ST',
    '01': '1DA',
    '14': '1DM',
    '13': '1DP',
    '02': '2DA',
    '59': '2DM',
    '12': '3DS',
    '07': 'ES',
    '08': 'EX',
    '54': 'EP',
}

class UPSRequest(UPSRequestBase):

    def __init__(self, debug_logger, username, password, access_number, prod_environment):
        self.debug_logger = debug_logger
        self.username = username
        self.password = password
        self.access_number = access_number

        self.restful_url = "https://onlinetools.ups.com/"
        if not prod_environment:
            self.restful_url = "https://wwwcie.ups.com/"

        self.sub_version = "1703"

        self.rate_restful = 'ship/v1/rating/Rate'
        self.ship_restful = 'ship/v1/shipments'
        self.void_restful = 'ship/v1/shipments/cancel/'
        self.time_in_transit = 'ship/v1/shipments/transittimes'
        self.track_restful = 'track/v1/details/'

    def _generate_header(self):
        headers = {
            "Username": self.username,
            "Password": self.password,
            "AccessLicenseNumber": self.access_number,
            "transactionSrc": self.username,
            "transId": "0",
            "Content-Type": 'application/json'
        }

        return headers

    @classmethod
    def set_package_detail(cls, package_detail,
                           insurance_info=None,
                           create_label=None, shipping_confirmation=None, weight_measurement='LBS'):
        packages = []
        for detail in package_detail:
            package = {
                'Packaging': {
                    "Description": "Package",
                    "Code": detail['packaging'] or '',
                }
            } if create_label else {
                'PackagingType': {
                    "Description": "Package",
                    "Code": detail['packaging'] or '',
                }
            }

            package.update({
                "Dimensions": {
                    "UnitOfMeasurement": {
                        "Code": "IN"
                    },
                    "Length": str(detail['length']) or '',
                    "Width": str(detail['width']) or '',
                    "Height": str(detail['height']) or '',
                },
                "PackageWeight": {
                    "UnitOfMeasurement": {
                        "Code": weight_measurement
                    },
                    "Weight": str(detail['weight'])
                }
            })

            if insurance_info or shipping_confirmation:
                package.update(PackageServiceOptions=dict())
                if insurance_info:
                    package["PackageServiceOptions"].update({
                        "DeclaredValue": {
                            "Type": {
                                "Code": "01",
                                "Description": "Insurance Cost",
                            },
                            "CurrencyCode": insurance_info['currency'],
                            "MonetaryValue": str(insurance_info['insurance_amount'])
                        }
                    })
                if shipping_confirmation:
                    package["PackageServiceOptions"].update({
                        "DeliveryConfirmation": dict(DCISType=shipping_confirmation)
                    })
            packages.append(package)

        return packages

    def _get_ship_partner_information(self, ship_partner, **kwargs):
        street = ship_partner.street
        if ship_partner.street2 and street:
            street += ', %s' % ship_partner.street2

        data = {
            "Name": (ship_partner.name or '')[:35],
            "Address": {
                "AddressLine": [street, ''],
                "City": ship_partner.city or '',
                "PostalCode": ship_partner.zip or '',
                "CountryCode": ship_partner.country_id.code or '',
                "StateProvinceCode": ship_partner.state_id.code or '',
            }
        }

        if ship_partner.phone:
            data.update({
                'Phone': {
                    'Number': ship_partner.phone or ''
                }
            })
        if kwargs:
            data = {**data, **kwargs}
        return data

    def get_time_in_transit(self, weight, service_type, ship_from, ship_to, ship_datetime,
                            insurance_detail=None, saturday_delivery=False):
        endpoint = self.restful_url + self.time_in_transit
        headers = self._generate_header()

        request_data = {
            "originCountryCode": ship_from.country_id.code or '',
            "originStateProvince": ship_from.state_id.code or '',
            "originCityName": ship_from.city or '',
            "originPostalCode": ship_from.zip or '',
            "destinationCountryCode": ship_to.country_id.code or '',
            "destinationStateProvince": ship_to.state_id.code or '',
            "destinationCityName": ship_to.city or '',
            "destinationPostalCode": ship_to.zip or '',
            "shipDate": ship_datetime['date'],
            "shipTime": ship_datetime['time'],
            "weight": str(weight),
            "weightUnitOfMeasure": "LBS",
        }

        if insurance_detail:
            request_data.update({
                "shipmentContentsValue": str(insurance_detail['insurance_amount']),
                "shipmentContentsCurrencyCode": insurance_detail['currency'],
            })

        result = {'estimated_date': 'N/A'}
        errors = []
        try:
            self.debug_logger(json.dumps(request_data), 'ups_request_time')
            response = requests.post(url=endpoint, data=json.dumps(request_data), headers=headers)
            self.debug_logger(response.content, 'ups_response_time')
            if response.status_code == 200:
                res_body = response.json()['emsResponse']
                services = res_body.get('services', [])
                if services:
                    try:
                        services_dict = {s['serviceLevel']: s['deliveryDate'] for s in services}
                        sc = SERVICE_LEVEL[service_type]
                        estimated_date = services_dict.get(sc, 'N/A')
                        if saturday_delivery:
                            estimated_date = services_dict.get('%sS' % sc, estimated_date)
                        result['estimated_date'] = estimated_date or 'N/A'
                    except Exception as e:
                        result['errors'] = self.get_error_message('0', 'Server Error:\n%s' % e)
            elif response.status_code == 206:
                res_body = response.json()['validationList']
                for k, v in res_body.items():
                    errors.append("%s: %s" % (k, v))
                result['errors'] = errors
            elif response.status_code in [400, 401, 402, 403, 406, 422, 423, 429]:
                errors = self.parse_errors(response)
                if errors:
                    result['errors'] = errors
            else:
                result['errors'] = response.content
        except IOError as e:
            result['errors'] = self.get_error_message('0', 'UPS Server Not Found:\n%s' % e)
        except Exception as e:
            result['errors'] = self.get_error_message('0', 'Server Error:\n%s' % e)
        return result

    def get_shipping_rate_and_delivery_time(self, shipment_info, package_detail, shipper, ship_from, ship_to, service_type,
                                            shipper_number, ship_datetime, insurance_detail, shipping_confirmation=None,
                                            shipping_info=None, is_return=False, is_residential=False):

        endpoint = self.restful_url + self.rate_restful
        if service_type and service_type not in ['92', '93', '07', '08', '54', '96']:
            endpoint += '?additionalinfo=timeintransit'

        headers = self._generate_header()

        delivery_time_info = {
            "PackageBillType": "03",
            "Pickup": {
                "Date": ship_datetime['date'],
                "Time": ship_datetime['time']
            }
        }
        ship_to_info = self._get_ship_partner_information(ship_to if not is_return else ship_from)
        if is_residential:
            ship_to_info['Address'].update({'ResidentialAddressIndicator': ''})

        ship_from_info = self._get_ship_partner_information(ship_from if not is_return else ship_to)

        weight_measurement = 'LBS'
        if service_type == '92':
            weight_measurement = 'OZS'

        total_weight = 0.0
        for detail in package_detail:
            total_weight += detail['weight']
        request_data = {
            "RateRequest": {
                "Request": {
                    "SubVersion": self.sub_version
                },
                "Shipment": {
                    "Shipper": {**self._get_ship_partner_information(shipper), **dict(ShipperNumber=shipper_number)},
                    "ShipTo": ship_to_info,
                    "ShipFrom": ship_from_info,
                    "Service": {
                        "Code": service_type or '',
                        "Description": "Service Code"
                    },
                    "Package": self.set_package_detail(package_detail, insurance_detail, False, shipping_confirmation, weight_measurement),
                    "ShipmentTotalWeight": {
                        "UnitOfMeasurement": {
                            "Code": weight_measurement
                        },
                        "Weight": str(total_weight)
                    },
                    "DeliveryTimeInformation": delivery_time_info,
                    "ShipmentRatingOptions": {
                        "NegotiatedRatesIndicator": "1"

                    }
                }
            }
        }

        if shipping_info:
            request_data["RateRequest"]["Shipment"] = self._create_shipment_other_options(
                shipment=request_data["RateRequest"]["Shipment"],
                other_options=shipping_info,
                request_type='rating',
                is_return=is_return
            )

        result = {}
        try:
            self.debug_logger(json.dumps(request_data), 'ups_request_rate')
            response = requests.post(url=endpoint, data=json.dumps(request_data), headers=headers)
            self.debug_logger(response.content, 'ups_response_rate')

            if response.status_code == 200:
                parsed = response.json()['RateResponse']
                result['currency_code'] = parsed['RatedShipment']['TotalCharges']['CurrencyCode']

                # Some users are qualified to receive negotiated rates
                negotiated_rate = 'NegotiatedRateCharges' in parsed['RatedShipment'] and \
                                  parsed['RatedShipment']['NegotiatedRateCharges']['TotalCharge'][
                                      'MonetaryValue'] or None

                result['price'] = negotiated_rate or parsed['RatedShipment']['TotalCharges']['MonetaryValue']
                result['price_without_discounts'] = 0.0
                if negotiated_rate:
                    result['price_without_discounts'] = parsed['RatedShipment']['TotalCharges']['MonetaryValue']
                # Get Estimated Date
                result['estimated_date'] = 'TimeInTransit' in parsed['RatedShipment'] and \
                                           parsed['RatedShipment']['TimeInTransit']['ServiceSummary'][
                                               'EstimatedArrival']['Arrival']['Date'] or None

            elif response.status_code in [400, 401, 402, 403, 406, 422, 423, 429]:
                errors = self.parse_errors(response)
                if errors:
                    result['errors'] = errors

        except IOError as e:
            result['errors'] = self.get_error_message('0', 'UPS Server Not Found:\n%s' % e)
        except Exception as e:
            result['errors'] = self.get_error_message('0', 'Server Error:\n%s' % e)
        return result

    @classmethod
    def _create_shipment_other_options(cls, shipment, other_options, request_type='shipping', is_return=False):
        """
        Add other options into the request
        :param dict shipment: "Shipment" part of the request
        :param dict other_options: dictionary containing options
        :param str request_type: either 'shipping' or 'rating'
        :param bool is_return: indicates whether the request is for returning label
        :return: dict "Shipment" part of the request after the addition
        """

        shipment_options = other_options["shipment_options"]
        label_options = other_options["label_options"]
        delivery_options = other_options["delivery_options"]
        shipment_service_options = {}

        # Shipment Options: This shipment requires additional handling
        if shipment_options.get('additional_handling'):
            for package in shipment["Package"]:
                package.update(AdditionalHandlingIndicator="")

        # Shipment Options: This order includes alcohol
        if shipment_options.get('alcohol'):
            shipment_service_options.setdefault("RestrictedArticles", {})
            shipment_service_options["RestrictedArticles"].update(AlcoholicBeveragesIndicator="")

        # Label Options: Include a return label with the outgoing shipping label
        if is_return and label_options.get('return_label'):
            shipment["ReturnService"] = dict(Code="9")
            for package in shipment["Package"]:
                package.update(Description="Return of courtesy")

        # Delivery Options: Collect payment on delivery (C.O.D.)
        if delivery_options.get('cod'):
            cod_type = delivery_options['cod']['type']
            for package in shipment["Package"]:
                package.setdefault("PackageServiceOptions", {})
                package["PackageServiceOptions"].update(COD={
                    "CODFundsCode": "0" if cod_type == 'cash' else "8" if cod_type == 'check' else "0",
                    "CODAmount": {
                        "CurrencyCode": "USD",
                        "MonetaryValue": str(delivery_options['cod']['amount'])
                    }
                })

        # Delivery Options: Saturday Delivery
        if delivery_options.get('saturday_delivery'):
            shipment_service_options.update(SaturdayDeliveryIndicator="")

        # Delivery Options: Driver may release package without signature
        if request_type == 'shipping' and delivery_options.get('optional_signature'):
            for package in shipment["Package"]:
                package.setdefault("PackageServiceOptions", {})
                package["PackageServiceOptions"]["ShipperReleaseIndicator"] = ""

        if shipment_service_options:
            shipment.update(ShipmentServiceOptions=shipment_service_options)

        return shipment

    def create_shipment_label(self, shipper_number, package_detail, shipper, ship_from, ship_to, service_type,
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

        ship_from_info = self._get_ship_partner_information(ship_from if not is_return else ship_to, **contact_ship_from_info)

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
                    "Height": "6",
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

    def void_label(self, shipment_id):
        endpoint = "%s%s%s" % (self.restful_url, self.void_restful, shipment_id)
        headers = self._generate_header()

        response = requests.delete(url=endpoint, headers=headers)
        self.debug_logger(response.content, 'ups_response_cancel')
        if response.status_code == 200:
            return {'success': True}
        else:
            errors = self.parse_errors(response)
            if errors:
                error_message = '\n'.join(err['error_message'] for err in errors)
            else:
                error_message = "Internal Server Error\nPlease try later!"

            return {
                'success': False,
                'error_message': error_message
            }

    def track_label(self, shipment_id):
        def get_status(pac):
            # The first activity will be the latest activity
            return pac['activity'][0]['status']

        endpoint = "%s%s%s" % (self.restful_url, self.track_restful, shipment_id)
        headers = self._generate_header()
        result = dict(success=False, msg='Unexpected response from UPS.')
        try:
            response = requests.get(url=endpoint, headers=headers)
            self.debug_logger(response.content, 'ups_response_track')
        except IOError as e:
            result = dict(success=False, msg=str(e))
        else:
            try:
                if response.status_code == 200:
                    res_shipment = response.json()['trackResponse']['shipment'][0]
                    if 'package' in res_shipment:
                        packages = res_shipment['package']
                        # Status type "D": Delivered
                        if all(get_status(package)['type'] == 'D' for package in packages):
                            msg = get_status(packages[0])['description']
                            result = dict(success=True, delivered=True, msg=msg)
                        else:
                            msg = '\n'.join(get_status(package)['description'] for package in packages)
                            result = dict(success=True, delivered=False, msg=msg)
                    else:
                        warning = res_shipment['warnings'][0]
                        result = dict(success=False, code=warning['code'], msg=warning['message'])
                else:
                    errors = self.parse_errors(response)
                    if errors:
                        result = dict(success=False, msg='\n'.join(err['error_message'] for err in errors))
            except (KeyError, IndexError):
                # Unexpected format from UPS
                pass
            except Exception as e:
                result = dict(success=False, msg=str(e))
        return result

    def parse_errors(self, response):
        errors = []
        if str(response.status_code)[0] == '4':
            parsed = response.json()['response']
            if 'errors' in parsed:
                parsed_err = parsed['errors']
                if isinstance(parsed_err, dict):
                    parsed_err = [parsed_err]
                for err in parsed_err:
                    if err.get('code') not in UPS_ERROR_MAP:
                        errors.append({'error_message': '%s - %s' % (err.get('code'), err.get('message'))})
                    else:
                        errors.append(self.get_error_message(err.get('code'), err.get('message')))
        return errors
