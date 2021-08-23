# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.
from odoo.addons.omni_fedex.models.fedex_request import FedexRequest


def new_add_package(self, weight_value, package_dimension={}, package_code=False, service_type=False, mode='shipping',
                 sequence_number=False, po_number=False, dept_number=False, reference=False, picking_number=False,
                 confirmation=False, insurance_amount=False, dry_ice_weight=False,
                 advanced_options={}, advanced_option_values={}, handling_fee=0.0):
    # [SRN-101] - Customer Reference = PO reference
    reference = po_number
    # [SRN-101]

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
    if package_code == 'YOUR_PACKAGING' and package_dimension['height'] != 0 \
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


FedexRequest._add_package = new_add_package
