# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from odoo.addons.delivery_fedex.models.fedex_request import FedexRequest as FedexRequestBase, LogPlugin
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
        self.debug_logger = debug_logger
        self.hasCommodities = False
        self.hasOnePackage = False
        self.response = False
        self.currency = False

        if request_type == "shipping":
            if not prod_environment:
                wsdl_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), '../api/test/ShipService_v25.wsdl')
            else:
                wsdl_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), '../api/prod/ShipService_v25.wsdl')
            self.start_shipping_transaction(wsdl_path)
            self.VersionId.Major = '25'

        elif request_type == "rating":
            if not prod_environment:
                wsdl_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), '../api/test/RateService_v26.wsdl')
            else:
                wsdl_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), '../api/prod/RateService_v26.wsdl')
            self.start_rating_transaction(wsdl_path)
            self.VersionId.Major = '26'

    def get_document(self):
        if self.response:
            if self.response.CompletedShipmentDetail:
                ShipmentDocuments = self.response.CompletedShipmentDetail.ShipmentDocuments
                if ShipmentDocuments:
                    return ShipmentDocuments[0].Parts[0].Image
        return False

    def set_pickup_detail(self, pickup_datetime):
        PickupDetail = self.factory.PickupDetail()
        PickupDetail.ReadyDateTime = pickup_datetime
        self.RequestedShipment.PickupDetail = PickupDetail

    def set_currency(self, currency):
        self.currency = currency
        self.RequestedShipment.PreferredCurrency = currency

    def set_insured_amount(self, amount):
        Money = self.factory.Money()
        Money.Currency = self.currency
        Money.Amount = amount
        self.RequestedShipment.TotalInsuredValue = Money

    def set_residential_recipient(self, residential):
        self.RequestedShipment.Recipient.Address.Residential = residential

    def set_residential_shipper(self, residential):
        self.RequestedShipment.Shipper.Address.Residential = residential

    def set_smartpost_detail(self, indicia, ancillary, hubId):
        smart_post_detail = self.factory.SmartPostShipmentDetail()
        smart_post_detail.HubId = hubId
        smart_post_detail.Indicia = indicia
        if ancillary != 'NONE':
            smart_post_detail.AncillaryEndorsement = ancillary
        self.RequestedShipment.SmartPostDetail = smart_post_detail


    # def shipment_label(self, label_format_type, image_type, label_stock_type, label_printing_orientation, label_order,
    #                    alcohol_shipment_label):
    #     LabelSpecification = self.factory.LabelSpecification()
    #     LabelSpecification.LabelFormatType = label_format_type
    #     LabelSpecification.ImageType = image_type
    #     LabelSpecification.LabelStockType = label_stock_type
    #     LabelSpecification.LabelPrintingOrientation = label_printing_orientation
    #     LabelSpecification.LabelOrder = label_order
    #
    #     if alcohol_shipment_label:
    #         LabelSpecification.CustomerSpecifiedDetail = self.factory.CustomerSpecifiedLabelDetail()
    #         LabelSpecification.CustomerSpecifiedDetail.RegulatoryLabels = self.factory.RegulatoryLabelContentDetail()
    #         LabelSpecification.CustomerSpecifiedDetail.RegulatoryLabels.Type = 'ALCOHOL_SHIPMENT_LABEL'
    #         LabelSpecification.CustomerSpecifiedDetail.RegulatoryLabels.GeneralOptions = 'CONTENT_ON_SHIPPING_LABEL_PREFERRED'
    #
    #     self.RequestedShipment.LabelSpecification = LabelSpecification

    # def _duties_payment(self, sender_party, responsible_account_number, payment_type):
    #     self.RequestedShipment.CustomsClearanceDetail = self.factory.CustomsClearanceDetail()
    #     self.RequestedShipment.CustomsClearanceDetail.DutiesPayment = self.factory.Payment()
    #     self.RequestedShipment.CustomsClearanceDetail.DutiesPayment.PaymentType = payment_type
    #
    #     Payor = self.factory.Payor()
    #     Payor.ResponsibleParty = self.factory.Party()
    #     Payor.ResponsibleParty.Address = self.factory.Address()
    #     Payor.ResponsibleParty.Address.CountryCode = sender_party.country_id.code
    #     Payor.ResponsibleParty.AccountNumber = responsible_account_number
    #     self.RequestedShipment.CustomsClearanceDetail.DutiesPayment.Payor = Payor

    def _shipping_charges_payment(self, shipping_charges_payment_account, payment_type='SENDER'):
        # payment type values: SENDER, RECIPIENT, THIRD_PARTY, ACCOUNT, COLLECT
        self.RequestedShipment.ShippingChargesPayment = self.factory.Payment()
        self.RequestedShipment.ShippingChargesPayment.PaymentType = payment_type
        Payor = self.factory.Payor()
        Payor.ResponsibleParty = self.factory.Party()
        Payor.ResponsibleParty.AccountNumber = shipping_charges_payment_account
        self.RequestedShipment.ShippingChargesPayment.Payor = Payor

    def _add_package(self, weight_value, package_dimension={}, package_code=False, service_type=False, mode='shipping',
                     sequence_number=False, po_number=False, dept_number=False, reference=False, picking_number=False,
                     confirmation=False, insurance_amount=False, dry_ice_weight=False,
                     advanced_options={}, advanced_option_values={}, handling_fee=0.0):
        package = self.factory.RequestedPackageLineItem()
        package_weight = self.factory.Weight()
        package_weight.Value = weight_value
        package_weight.Units = self.RequestedShipment.TotalWeight.Units

        if insurance_amount:
            package_insured = self.factory.Money()
            package_insured.Currency = self.currency
            package_insured.Amount = insurance_amount
            package.InsuredValue = package_insured

        special_services_type = []
        package.SpecialServicesRequested = self.factory.PackageSpecialServicesRequested()
        # if advanced_options.get('shipping_include_dry_ice'):
        #     package.SpecialServicesRequested.DryIceWeight = self.factory.Weight()
        #     package.SpecialServicesRequested.DryIceWeight.Value = advanced_option_values.get('dry_ice_weight')
        #     package.SpecialServicesRequested.DryIceWeight.Units = 'KG'

        if confirmation:
            special_services_type.append('SIGNATURE_OPTION')
            package.SpecialServicesRequested.SignatureOptionDetail = self.factory.SignatureOptionDetail()
            package.SpecialServicesRequested.SignatureOptionDetail.OptionType = confirmation

        # if advanced_options.get('shipping_include_alcohol'):
        #     package.SpecialServicesRequested.AlcoholDetail = self.factory.AlcoholDetail()
        #     package.SpecialServicesRequested.AlcoholDetail.RecipientType = self.factory.AlcoholRecipientType('CONSUMER')

        # if advanced_options.get('shipping_cod'):
        #     package.SpecialServicesRequested.CodDetail = self.factory.CodDetail()
        #     package.SpecialServicesRequested.CodDetail.CodCollectionAmount = self.factory.Money()
        #     package.SpecialServicesRequested.CodDetail.CodCollectionAmount.Currency = self.currency
        #     package.SpecialServicesRequested.CodDetail.CodCollectionAmount.Amount = advanced_option_values.get('cod_amount')
        #     package.SpecialServicesRequested.CodDetail.CollectionType = advanced_option_values.get('cod_payment_type')
        #     package.SpecialServicesRequested.CodDetail.AddTransportationChargesDetail = self.factory.CodAddTransportationChargesDetail()
        #     package.SpecialServicesRequested.CodDetail.AddTransportationChargesDetail.RateTypeBasis = 'LIST'
        #     package.SpecialServicesRequested.CodDetail.AddTransportationChargesDetail.ChargeBasis = 'COD_SURCHARGE'
        #     package.SpecialServicesRequested.CodDetail.AddTransportationChargesDetail.ChargeBasisLevel = 'CURRENT_PACKAGE'

        if special_services_type:
            package.SpecialServicesRequested.SpecialServiceTypes = special_services_type

        package.PhysicalPackaging = 'BOX'
        if package_code == 'YOUR_PACKAGING' and package_dimension['height'] != 0\
                and package_dimension['width'] != 0 and package_dimension['length'] != 0:
            package.Dimensions = self.factory.Dimensions()
            package.Dimensions.Height = int(package_dimension['height'])
            package.Dimensions.Width = int(package_dimension['width'])
            package.Dimensions.Length = int(package_dimension['length'])
            package.Dimensions.Units = "IN"
        if po_number:
            po_reference = self.factory.CustomerReference()
            po_reference.CustomerReferenceType = 'P_O_NUMBER'
            po_reference.Value = po_number
            package.CustomerReferences.append(po_reference)
        if dept_number:
            dept_reference = self.factory.CustomerReference()
            dept_reference.CustomerReferenceType = 'DEPARTMENT_NUMBER'
            dept_reference.Value = dept_number
            package.CustomerReferences.append(dept_reference)
        if reference:
            customer_reference = self.factory.CustomerReference()
            customer_reference.CustomerReferenceType = 'CUSTOMER_REFERENCE'
            customer_reference.Value = reference
            package.CustomerReferences.append(customer_reference)
        # if picking_number:
        #     picking_ref = self.factory.CustomerReference()
        #     picking_ref.CustomerReferenceType = 'PACKING_SLIP_NUMBER'
        #     picking_ref.Value = picking_number
        #     package.CustomerReferences.append(picking_ref)

        package.Weight = package_weight
        if mode == 'rating':
            package.GroupPackageCount = 1
        if sequence_number:
            package.SequenceNumber = sequence_number
        else:
            self.hasOnePackage = True

        # Add Handling fee
        if handling_fee > 0:
            handling_charge_detail = self.factory.VariableHandlingChargeDetail()
            fixed_value = self.factory.Money()
            fixed_value.Currency = self.currency
            fixed_value.Amount = handling_fee
            handling_charge_detail.FixedValue = fixed_value
            package.VariableHandlingChargeDetail = handling_charge_detail

        if mode == 'rating':
            self.RequestedShipment.RequestedPackageLineItems.append(package)
        else:
            self.RequestedShipment.RequestedPackageLineItems = package

    def shipment_request(self, dropoff_type, service_type, packaging_type, overall_weight_unit,
                         pickup_datetime=datetime.now()):
        self.RequestedShipment = self.factory.RequestedShipment()
        self.RequestedShipment.ShipTimestamp = pickup_datetime
        self.RequestedShipment.DropoffType = dropoff_type
        self.RequestedShipment.ServiceType = service_type
        self.RequestedShipment.PackagingType = packaging_type
        # Resquest estimation of duties and taxes for international shipping
        if service_type in ['INTERNATIONAL_ECONOMY', 'INTERNATIONAL_PRIORITY']:
            self.RequestedShipment.EdtRequestType = 'ALL'
        else:
            self.RequestedShipment.EdtRequestType = 'NONE'
        self.RequestedShipment.PackageCount = 0
        self.RequestedShipment.TotalWeight = self.factory.Weight()
        self.RequestedShipment.TotalWeight.Units = overall_weight_unit
        self.RequestedShipment.TotalWeight.Value = 0
        self.listCommodities = []

        # if advanced_options.get('shipping_include_dry_ice'):
        #     self.RequestedShipment.SpecialServicesRequested.ShipmentDryIceDetail = self.factory.ShipmentDryIceDetail()
        #     self.RequestedShipment.SpecialServicesRequested.ShipmentDryIceDetail.PackageCount = 1
        #     self.RequestedShipment.SpecialServicesRequested.ShipmentDryIceDetail.TotalWeight = self.factory.Weight()
        #     self.RequestedShipment.SpecialServicesRequested.ShipmentDryIceDetail.TotalWeight.Value = advanced_option_values.get('dry_ice_weight')
        #     self.RequestedShipment.SpecialServicesRequested.ShipmentDryIceDetail.TotalWeight.Units = 'KG'
            # ProcessingOptions = self.factory.ShipmentDryIceProcessingOptionsRequested()
            # ProcessingOptions.Options = 'SHIPMENT_LEVEL_DRY_ICE_ONLY'
            # self.RequestedShipment.SpecialServicesRequested.ShipmentDryIceDetail.ProcessingOptions = ProcessingOptions

    def shipment_request_special_services(self, advanced_options, advanced_option_values):
        shipment_special_service_types = []
        self.RequestedShipment.SpecialServicesRequested = self.factory.ShipmentSpecialServicesRequested()
        if advanced_options.get('shipping_saturday_delivery'):
            shipment_special_service_types.append('SATURDAY_DELIVERY')

        if advanced_options.get('shipping_cod'):
            shipment_special_service_types.append('COD')
            self.RequestedShipment.SpecialServicesRequested.CodDetail = self.factory.CodDetail()
            self.RequestedShipment.SpecialServicesRequested.CodDetail.CodCollectionAmount = self.factory.Money()
            self.RequestedShipment.SpecialServicesRequested.CodDetail.CodCollectionAmount.Currency = self.currency
            self.RequestedShipment.SpecialServicesRequested.CodDetail.CodCollectionAmount.Amount = advanced_option_values.get(
                'cod_amount')
            self.RequestedShipment.SpecialServicesRequested.CodDetail.CollectionType = self.factory.CodCollectionType(advanced_option_values.get('cod_payment_type'))

        if shipment_special_service_types:
            self.RequestedShipment.SpecialServicesRequested.SpecialServiceTypes = shipment_special_service_types

    def process_shipment(self):
        if self.hasCommodities:
            self.RequestedShipment.CustomsClearanceDetail.Commodities = self.listCommodities
        formatted_response = {'tracking_number': 0.0,
                              'price': {},
                              'price_without_discounts': {},
                              'insurance': {},
                              'master_tracking_id': None,
                              'date': None}

        try:
            self.response = self.client.service.processShipment(WebAuthenticationDetail=self.WebAuthenticationDetail,
                                                                ClientDetail=self.ClientDetail,
                                                                TransactionDetail=self.TransactionDetail,
                                                                Version=self.VersionId,
                                                                RequestedShipment=self.RequestedShipment)

            if (self.response.HighestSeverity != 'ERROR' and self.response.HighestSeverity != 'FAILURE'):
                formatted_response['tracking_number'] = self.response.CompletedShipmentDetail.CompletedPackageDetails[0].TrackingIds[0].TrackingNumber
                if 'CommitDate' in self.response.CompletedShipmentDetail.OperationalDetail:
                    formatted_response['date'] = self.response.CompletedShipmentDetail.OperationalDetail.CommitDate
                else:
                    formatted_response['date'] = date.today()

                if (self.RequestedShipment.RequestedPackageLineItems.SequenceNumber == self.RequestedShipment.PackageCount) or self.hasOnePackage:
                    completed_shipment_detail = self.response.CompletedShipmentDetail
                    if 'ShipmentRating' in completed_shipment_detail and completed_shipment_detail.ShipmentRating:
                        for rating in completed_shipment_detail.ShipmentRating.ShipmentRateDetails:
                            price = rating.TotalNetFedExCharge.Amount
                            formatted_response['price'][rating.TotalNetFedExCharge.Currency] = self._compute_handling_charges(price, rating)
                            price_without_discounts = self._compute_price_without_discount(rating)
                            formatted_response['price_without_discounts'][
                                rating.TotalNetFedExCharge.Currency] = price_without_discounts

                            insurance_flag = False
                            insurance_amount = 0.0
                            for surcharge in rating.Surcharges:
                                if surcharge.SurchargeType == 'INSURED_VALUE':
                                    insurance_amount = float(surcharge.Amount.Amount)
                                    formatted_response['insurance'][surcharge.Amount.Currency] = insurance_amount
                                    insurance_flag = True
                            if not insurance_flag:
                                formatted_response['insurance']['USD'] = 0.0

                            if 'CurrencyExchangeRate' in rating and rating.CurrencyExchangeRate:
                                price = rating.TotalNetFedExCharge.Amount
                                formatted_response['price'][rating.CurrencyExchangeRate.FromCurrency] = self._compute_handling_charges(price, rating) / rating.CurrencyExchangeRate.Rate
                                price_without_discounts = self._compute_price_without_discount(rating)
                                formatted_response['price_without_discounts'][
                                    rating.CurrencyExchangeRate.FromCurrency] = price_without_discounts / rating.CurrencyExchangeRate.Rate

                                if insurance_flag:
                                    formatted_response['insurance'][rating.CurrencyExchangeRate.FromCurrency] = float(insurance_amount / rating.CurrencyExchangeRate.Rate)
                    else:
                        formatted_response['price']['USD'] = False

                if 'MasterTrackingId' in self.response.CompletedShipmentDetail:
                    formatted_response['master_tracking_id'] = self.response.CompletedShipmentDetail.MasterTrackingId.TrackingNumber

            else:
                errors_message = '\n'.join([("%s: %s" % (n.Code, n.Message)) for n in self.response.Notifications if (n.Severity == 'ERROR' or n.Severity == 'FAILURE')])
                formatted_response['errors_message'] = errors_message

            if any([n.Severity == 'WARNING' for n in self.response.Notifications]):
                warnings_message = '\n'.join([("%s: %s" % (n.Code, n.Message)) for n in self.response.Notifications if n.Severity == 'WARNING'])
                formatted_response['warnings_message'] = warnings_message

        except Fault as fault:
            formatted_response['errors_message'] = fault
        except IOError:
            formatted_response['errors_message'] = "Fedex Server Not Found"

        return formatted_response

    def _compute_price_without_discount(self, data):
        discounts_amount = data.TotalFreightDiscounts.Amount
        price_without_discounts = 0
        if discounts_amount > 0:
            base_price = data.TotalBaseCharge.Amount
            fuel_charges = base_price * data.FuelSurchargePercent / 100
            surcharges = data.Surcharges
            total_surcharge_without_fuel = sum([e.Amount.Amount
                                               for e in list(filter(lambda e: e.SurchargeType != 'FUEL', surcharges))])

            price_without_discounts = base_price + fuel_charges + total_surcharge_without_fuel
            price_without_discounts = self._compute_handling_charges(price_without_discounts, data)
        return price_without_discounts

    def _compute_handling_charges(self, price, data):
        if data.TotalVariableHandlingCharges and data.TotalVariableHandlingCharges.VariableHandlingCharge:
            price += data.TotalVariableHandlingCharges.VariableHandlingCharge.Amount
        return price

    def rate(self, carrier_codes=[], service_option_type=[], return_time_in_transit=False):
        """

        (CarrierCodeType){
           FDXC = "FDXC"
           FDXE = "FDXE"
           FDXG = "FDXG"
           FXCC = "FXCC"
           FXFR = "FXFR"
           FXSP = "FXSP"
        }

        (ServiceOptionType){
           FEDEX_ONE_RATE = "FEDEX_ONE_RATE"
           FREIGHT_GUARANTEE = "FREIGHT_GUARANTEE"
           SATURDAY_DELIVERY = "SATURDAY_DELIVERY"
           SMART_POST_ALLOWED_INDICIA = "SMART_POST_ALLOWED_INDICIA"
           SMART_POST_HUB_ID = "SMART_POST_HUB_ID"
         }
        :param carrier_codes: a list of CarrierCodeType
        :param service_option_type: a list of ServiceOptionType
        :param time_in_transit: boolean
        :return:
        """
        formatted_response = {'price': {}, 'price_without_discounts': {}}
        del self.ClientDetail['Region']
        if self.hasCommodities:
            self.RequestedShipment.CustomsClearanceDetail.Commodities = self.listCommodities

        try:
            self.response = self.client.service.getRates(WebAuthenticationDetail=self.WebAuthenticationDetail,
                                                         ClientDetail=self.ClientDetail,
                                                         TransactionDetail=self.TransactionDetail,
                                                         Version=self.VersionId,
                                                         RequestedShipment=self.RequestedShipment,
                                                         VariableOptions=service_option_type,
                                                         CarrierCodes=carrier_codes,
                                                         ReturnTransitAndCommit=return_time_in_transit)

            if (self.response.HighestSeverity != 'ERROR' and self.response.HighestSeverity != 'FAILURE'):
                if not getattr(self.response, "RateReplyDetails", False):
                    raise Exception("No rating found")
                reply = self.response.RateReplyDetails[0]
                try:
                    if reply['ServiceType'] in ['FEDEX_GROUND', 'GROUND_HOME_DELIVERY']:
                        formatted_response['estimated_delivery_time'] = reply['TransitTime'].replace('_', ' Business ').title()
                    else:
                        formatted_response['estimated_delivery_time'] = reply['DeliveryTimestamp']
                except Exception as e:
                    _logger.error("Cannot get Estimated Transit Time: %s" % e)
                    formatted_response['estimated_delivery_time'] = 'N/A'
                for rating in reply.RatedShipmentDetails:
                    data = rating.ShipmentRateDetail
                    formatted_response['price'][data.TotalNetFedExCharge.Currency] = \
                        self._compute_handling_charges(data.TotalNetFedExCharge.Amount, data)
                    price_without_discounts = self._compute_price_without_discount(data)
                    formatted_response['price_without_discounts'][data.TotalNetFedExCharge.Currency] = price_without_discounts
                if len(self.response.RateReplyDetails[0].RatedShipmentDetails) == 1:
                    if 'CurrencyExchangeRate' in self.response.RateReplyDetails[0].RatedShipmentDetails[
                        0].ShipmentRateDetail and \
                            self.response.RateReplyDetails[0].RatedShipmentDetails[0].ShipmentRateDetail[
                                'CurrencyExchangeRate']:
                        data = self.response.RateReplyDetails[0].RatedShipmentDetails[
                            0].ShipmentRateDetail
                        currency = data.CurrencyExchangeRate.FromCurrency
                        exchange_rate = data.CurrencyExchangeRate.Rate
                        price = self._compute_handling_charges(data.TotalNetFedExCharge.Amount, data)
                        formatted_response['price'][currency] = price / exchange_rate

                        price_without_discounts = self._compute_price_without_discount(data)
                        formatted_response['price_without_discounts'][currency] = price_without_discounts / exchange_rate
            else:
                errors_message = '\n'.join([("%s: %s" % (n.Code, n.Message)) for n in self.response.Notifications if (n.Severity == 'ERROR' or n.Severity == 'FAILURE')])
                formatted_response['errors_message'] = errors_message

            if any([n.Severity == 'WARNING' for n in self.response.Notifications]):
                warnings_message = '\n'.join([("%s: %s" % (n.Code, n.Message)) for n in self.response.Notifications if n.Severity == 'WARNING'])
                formatted_response['warnings_message'] = warnings_message

        except Fault as fault:
            formatted_response['errors_message'] = fault
        except IOError:
            formatted_response['errors_message'] = "Fedex Server Not Found"
        except Exception as e:
            formatted_response['errors_message'] = e.args[0]

        return formatted_response