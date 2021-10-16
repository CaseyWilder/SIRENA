# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

import requests
import json
from datetime import datetime

class CapitalInsuranceRequest:
    def __init__(self, bearer, client_id, client_secret, partner_id):
        self.bearer = bearer
        self.client_id = client_id
        self.client_secret = client_secret
        self.partner_id = partner_id

        self.restful_url = "https://upscapi.ams1907.com/apis/list-extstg/"

        self.create_restful = 'quote/v2'
        self.confirm_restful = 'coverage/v2'

    def _generate_header(self):
        headers = {
            "Content-Type": 'application/json',
            "Bearer": self.bearer,
            "X-IBM-Client-Id": self.client_id,
            "X-IBM-Client-Secret": self.client_secret,
        }
        return headers

    def _set_origin_address(self, address):
        return {
            "originAddress1": address.street,
            "originAddress2": address.street2 or ".",
            "originCity": address.city,
            "originState": address.state_id.code,
            "originPostalCode": address.zip,
            "originCountry": address.country_id.code
        }

    def _set_destination_address(self, address):
        return {
            "destinationAddress1": address.street,
            "destinationAddress2": address.street2 or ".",
            "destinationCity": address.city,
            "destinationState": address.state_id.code,
            "destinationPostalCode": address.zip,
            "destinationCountry": address.country_id.code
        }

    def create_insurance_quote(self, insurance_details):
        if not isinstance(insurance_details, dict):
            return {
                "result": "ERROR",
                "error_message": "Invalid insurance details!"
            }
        if "tracking_number" not in insurance_details or "insured_value" not in insurance_details:
            return {
                "result": "ERROR",
                "error_message": "Missing shipment's tracking number and/or shipment's insured value!"
            }
        if "origin_address" not in insurance_details:
            return {
                "result": "ERROR",
                "error_message": "Missing Shipping From address!"
            }
        if "destination_address" not in insurance_details:
            return {
                "result": "ERROR",
                "error_message": "Missing Shipping To address!"
            }

        headers = self._generate_header()
        api_endpoint = self.restful_url + self.create_restful
        body = {
            "status": "UNCONFIRMED",
            "partnerId": self.partner_id,
            "shipDate": insurance_details.get('ship_date', datetime.today().strftime('%Y-%m-%d')),  # Format: "YYYY-MM-DD"
            "bol": insurance_details['tracking_number'],
            "insuredValue": str(insurance_details['insured_value']),
            "carrier": "FEDG",
            "shipmentType": "3",
            "packageQuantity": str(insurance_details.get('package_quantity', '1')),
        }
        body.update(self._set_origin_address(insurance_details['origin_address']))
        body.update(self._set_destination_address(insurance_details['destination_address']))

        try:
            response = requests.post(url=api_endpoint, data=json.dumps(body), headers=headers)
            parsed = response.json()

            if response.status_code == 200:
                quote_id = parsed['quoteId']
                premium_amount = parsed['premiumAmount']
            elif response.status_code in [400, 401, 404, 500]:
                error_message = ""
                for error in parsed['errors']:
                    error_message += error['errorMessage'] + "\n"
                return {
                    "result": "ERROR",
                    "error_message": error_message
                }

        except IOError as e:
            return {
                "result": "ERROR",
                "error_message": f'UPS Server Not Found: {e}',
            }
        except Exception as e:
            return {
                "result": "ERROR",
                "error_message": f'Server Error: {e}',
            }

        return {
            "result": "SUCCESS",
            "quoteId": quote_id,
            "premiumAmount": premium_amount
        }

    def confirm_insurance_quote(self, quote_id, tracking_number):
        if not quote_id or not tracking_number:
            return {
                "result": "ERROR",
                "error_message": "Invalid method parameters!"
            }

        api_endpoint = self.restful_url + self.confirm_restful
        body = {
            "quoteId": quote_id,
            "partnerId": self.partner_id,
            "bol": tracking_number,
            "status": "CONFIRMED"
        }

        try:
            response = requests.post(url=api_endpoint, data=json.dumps(body), headers=self._generate_header())
            parsed = response.json()

            if response.status_code == 200:
                premium_amount = parsed['premiumAmount']
            elif response.status_code in [400, 401, 404, 500]:
                error_message = ""
                for error in parsed['errors']:
                    error_message += error['errorMessage'] + "\n"
                return {
                    "result": "ERROR",
                    "error_message": error_message
                }

        except IOError as e:
            return {
                "result": "ERROR",
                "error_message": f'UPS Server Not Found: {e}',
            }
        except Exception as e:
            return {
                "result": "ERROR",
                "error_message": f'Server Error: {e}',
            }

        return {
            "result": "SUCCESS",
            "premiumAmount": premium_amount
        }

    def void_insurance_quote(self, quote_id, tracking_number):
        if not quote_id or not tracking_number:
            return {
                "result": "ERROR",
                "error_message": "Invalid method parameters!"
            }

        api_endpoint = self.restful_url + self.confirm_restful
        body = {
            "quoteId": quote_id,
            "partnerId": self.partner_id,
            "bol": tracking_number,
            "status": "VOID"
        }

        try:
            response = requests.post(url=api_endpoint, data=json.dumps(body), headers=self._generate_header())
            parsed = response.json()

            if response.status_code == 200:
                premium_amount = parsed['premiumAmount']
            elif response.status_code in [400, 401, 404, 500]:
                error_message = ""
                for error in parsed['errors']:
                    error_message += error['errorMessage'] + "\n"
                return {
                    "result": "ERROR",
                    "error_message": error_message
                }

        except IOError as e:
            return {
                "result": "ERROR",
                "error_message": f'UPS Server Not Found: {e}',
            }
        except Exception as e:
            return {
                "result": "ERROR",
                "error_message": f'Server Error: {e}',
            }

        return {
            "result": "SUCCESS",
            "premiumAmount": premium_amount
        }
