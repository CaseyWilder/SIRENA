# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from odoo.addons.omni_fedex.models.fedex_request import FedexRequest as FedexRequestBase, LogPlugin
from datetime import datetime, date
import os
import logging
from zeep import Client
from zeep.exceptions import Fault

_logger = logging.getLogger(__name__)

def egress(self, envelope, http_headers, operation, binding_options):
    op = str(operation)
    self.debug_logger(envelope, 'fedex_request - {}'.format(op[:op.find('(')] if '(' in op else op))
    return envelope, http_headers


def ingress(self, envelope, http_headers, operation):
    op = str(operation)
    self.debug_logger(envelope, 'fedex_response - {}'.format(op[:op.find('(')] if '(' in op else op))
    return envelope, http_headers

LogPlugin.egress = egress
LogPlugin.ingress = ingress


class FedexRequest(FedexRequestBase):

    def __init__(self, debug_logger, request_type="shipping", prod_environment=False):
        super(FedexRequestBase, self).__init__(debug_logger, request_type, prod_environment)
        if request_type == 'validating':
            if not prod_environment:
                wsdl_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), '../api/test/AddressValidationService_v4.wsdl')
            else:
                wsdl_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), '../api/prod/AddressValidationService_v4.wsdl')
            self.start_validating_transaction(wsdl_path)

    def start_validating_transaction(self, wsdl_path):
        self.client = Client('file:///%s' % wsdl_path.lstrip('/'), plugins=[LogPlugin(self.debug_logger)])
        self.factory = self.client.type_factory("ns0")
        self.VersionId = self.factory.VersionId()
        self.VersionId.ServiceId = 'aval'
        self.VersionId.Major = '4'
        self.VersionId.Intermediate = '0'
        self.VersionId.Minor = '0'

    def add_address_to_validation_request(self, delivery_address):
        address_to_validate = self.factory.AddressToValidate()
        address_to_validate.ClientReferenceId = 'Put res_partner\'s name here (not required)'
        address = self.factory.Address()
        address.StreetLines = [delivery_address.street, delivery_address.street2]
        address.City = delivery_address.city
        address.StateOrProvinceCode = delivery_address.state_id.code
        address.PostalCode = delivery_address.zip
        address.CountryCode = delivery_address.country_id.code
        address_to_validate.Address = address
        self.AddressesToValidate = address_to_validate

    def process_validation(self, delivery_address):
        self.add_address_to_validation_request(delivery_address)
        formatted_response = {'current_address': {},
                              'validated_address': {},
                              'address_classification': ''}
        try:
            self.response = self.client.service.addressValidation(WebAuthenticationDetail=self.WebAuthenticationDetail,
                                                                  ClientDetail=self.ClientDetail,
                                                                  Version=self.VersionId,
                                                                  AddressesToValidate=self.AddressesToValidate)
        except Fault as fault:
            formatted_response['errors_message'] = fault
        except IOError:
            formatted_response['errors_message'] = "Fedex Server Not Found"

        # Handle and parse AddressValidationReply
        formatted_response['status'] = self.response.HighestSeverity

        if self.response.HighestSeverity == 'ERROR' or self.response.HighestSeverity == 'FAILURE':
            errors_message = '\n'.join([("%s: %s" % (n.Code, n.Message)) for n in self.response.Notifications if
                                        (n.Severity == 'ERROR' or n.Severity == 'FAILURE')])
            formatted_response['errors_message'] = errors_message
            return formatted_response

        if self.response.AddressResults[0] is None:
            formatted_response['errors_message'] = 'Something went wrong, please try again!'
            return formatted_response

        if any([n.Severity == 'WARNING' for n in self.response.Notifications]):
            warnings_message = '\n'.join(
                [("%s: %s" % (n.Code, n.Message)) for n in self.response.Notifications if n.Severity == 'WARNING'])
            formatted_response['warnings_message'] = warnings_message

        formatted_response['matching_state'] = self.response.AddressResults[0].State
        formatted_response['validated_address'] = self.response.AddressResults[0].EffectiveAddress
        formatted_response['address_classification'] = self.response.AddressResults[0].Classification
        formatted_response['current_address'] = {'StreetLines': [delivery_address.street, delivery_address.street2 or ''],
                                                 'City': delivery_address.city,
                                                 'StateOrProvinceCode': delivery_address.state_id.code,
                                                 'PostalCode': delivery_address.zip,
                                                 'CountryCode': delivery_address.country_id.code}
        return formatted_response
