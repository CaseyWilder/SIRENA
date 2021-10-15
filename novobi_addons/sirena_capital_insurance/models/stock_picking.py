from odoo import api, fields, models, _

from ..utils.capital_insurance_request import CapitalInsuranceRequest


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    second_fedex_service_type = fields.Selection(related='second_delivery_carrier_id.fedex_service_type')

    capital_insurance_value = fields.Float(string='Capital Insured Value')
    capital_insurance_quote_id = fields.Char(string='Insurance Quote ID')
    capital_insurance_premium_amount = fields.Char(string='Insurance Premium Amount')

    second_capital_insurance_quote_id = fields.Char(string='Insurance Quote ID')
    second_capital_insurance_premium_amount = fields.Char(string='Insurance Premium Amount')

    def action_create_label(self):
        result = super().action_create_label()

        if self.shipping_account_id.provider != 'fedex' or self.capital_insurance_value <= 0.0:
            return result

        insurance_request = CapitalInsuranceRequest(bearer=self.shipping_account_id.capital_bearer or '',
                                                    client_id=self.shipping_account_id.capital_client_id or '',
                                                    client_secret=self.shipping_account_id.capital_client_secret or '',
                                                    partner_id=self.shipping_account_id.capital_partner_id or '')
        if self.shipping_options == 'option1':
            if self.fedex_service_type not in ['GROUND_HOME_DELIVERY', 'FEDEX_GROUND']:
                return result
            insurance_details = {
                "ship_date": self.shipping_date.strftime('%Y-%m-%d'),
                "tracking_number": self.carrier_tracking_ref if not self.is_mul_packages else self.picking_package_ids[0].carrier_tracking_ref,  # create quote for master package only
                "insured_value": str(self.capital_insurance_value),
                "package_quantity": "1" if not self.is_mul_packages else str(len(self.picking_package_ids)),
                "origin_address": self.partner_id,
                "destination_address": self.company_id.partner_id,
            }
        else:
            if self.second_fedex_service_type not in ['GROUND_HOME_DELIVERY', 'FEDEX_GROUND']:
                return result
            insurance_details = {
                "ship_date": self.second_shipping_date.strftime('%Y-%m-%d'),
                "tracking_number": self.second_carrier_tracking_ref,
                "insured_value": str(self.capital_insurance_value),
                "package_quantity": "1",
                "origin_address": self.partner_id,
                "destination_address": self.company_id.partner_id,
            }

        insurance_result = insurance_request.create_insurance_quote(insurance_details=insurance_details)
        if insurance_result['result'] == 'ERROR':
            log_message = (_("Shipping Option %s<br/>Failed to create UPS Capital Insurance: %s") % ("1" if self.shipping_options == 'option1' else "2", insurance_result['error_message']))
            self.message_post(body=log_message)
        elif insurance_result['result'] == 'SUCCESS':
            quote_id = str(insurance_result['quoteId'])
            premium_amount = str(insurance_result['premiumAmount'])
            content = "Shipping Option %s<br/><b>Insurance Quote ID: </b>%s<br/><b>Insurance Premium Amount: </b>%s"
            if self.shipping_options == 'option1':
                self.update({
                    'capital_insurance_quote_id': quote_id,
                    'capital_insurance_premium_amount': premium_amount
                })
                log_message = (_(content) % ("1", quote_id, premium_amount))
                self.message_post(body=log_message)
            else:
                self.update({
                    'second_capital_insurance_quote_id': quote_id,
                    'second_capital_insurance_premium_amount': premium_amount
                })
                log_message = (_(content) % ("2", quote_id, premium_amount))
                self.message_post(body=log_message)
        self.capital_insurance_value = 0.0  # reset this field to reuse for the next shipping option

        return result

    def button_validate(self):
        result = super().button_validate()

        if self.picking_type_code != 'outgoing':
            return result

        if not self.label_status:
            return result

        if self.shipping_account_id.provider != 'fedex':
            return result

        insurance_request = CapitalInsuranceRequest(bearer=self.shipping_account_id.capital_bearer or '',
                                                    client_id=self.shipping_account_id.capital_client_id or '',
                                                    client_secret=self.shipping_account_id.capital_client_secret or '',
                                                    partner_id=self.shipping_account_id.capital_partner_id or '')

        if self.is_create_label and self.fedex_service_type in ['GROUND_HOME_DELIVERY', 'FEDEX_GROUND']:
            if not self.capital_insurance_quote_id:
                log_message = (_("Shipping Option 1<br/>Failed to confirm UPS Capital Insurance: Missing Insurance Quote ID!"))
                self.message_post(body=log_message)
            else:
                insurance_result = insurance_request.confirm_insurance_quote(self.capital_insurance_quote_id, self.carrier_tracking_ref if not self.is_mul_packages else self.picking_package_ids[0].carrier_tracking_ref)
                if insurance_result['result'] == 'ERROR':
                    log_message = (_("Shipping Option 1<br/>Failed to confirm UPS Capital Insurance: %s") % (insurance_result['error_message']))
                    self.message_post(body=log_message)
                elif insurance_result['result'] == 'SUCCESS':
                    log_message = (_("UPS Capital Insurance is confirmed for shipping option 1"))
                    self.message_post(body=log_message)

        if self.second_is_create_label and self.second_fedex_service_type in ['GROUND_HOME_DELIVERY', 'FEDEX_GROUND']:
            if not self.second_capital_insurance_quote_id:
                log_message = (_("Shipping Option 2<br/>Failed to confirm UPS Capital Insurance: Missing Insurance Quote ID!"))
                self.message_post(body=log_message)
            else:
                second_insurance_result = insurance_request.confirm_insurance_quote(self.second_capital_insurance_quote_id, self.second_carrier_tracking_ref)
                if second_insurance_result['result'] == 'ERROR':
                    log_message = (_("Shipping Option 2<br/>Failed to confirm UPS Capital Insurance: %s") % (second_insurance_result['error_message']))
                    self.message_post(body=log_message)
                elif second_insurance_result['result'] == 'SUCCESS':
                    log_message = (_("UPS Capital Insurance is confirmed for shipping option 2"))
                    self.message_post(body=log_message)

        return result

    def button_void_label(self):
        """
        Save fields' values before getting reset by super()
        """
        carrier_tracking_ref = self.carrier_tracking_ref if not self.is_mul_packages else self.picking_package_ids[0].carrier_tracking_ref
        second_carrier_tracking_ref = self.second_carrier_tracking_ref
        fedex_service_type = self.fedex_service_type
        second_fedex_service_type = self.second_fedex_service_type

        result = super().button_void_label()

        if self.shipping_account_id.provider != 'fedex':
            return result

        insurance_request = CapitalInsuranceRequest(bearer=self.shipping_account_id.capital_bearer or '',
                                                    client_id=self.shipping_account_id.capital_client_id or '',
                                                    client_secret=self.shipping_account_id.capital_client_secret or '',
                                                    partner_id=self.shipping_account_id.capital_partner_id or '')

        if self.is_void_first_label and fedex_service_type in ['GROUND_HOME_DELIVERY', 'FEDEX_GROUND']:
            if not self.capital_insurance_quote_id:
                log_message = (_("Shipping Option 1<br/>Failed to void UPS Capital Insurance: Missing Insurance Quote ID!"))
                self.message_post(body=log_message)
            else:
                insurance_result = insurance_request.void_insurance_quote(self.capital_insurance_quote_id, carrier_tracking_ref)
                if insurance_result['result'] == 'ERROR':
                    log_message = (_("Shipping Option 1<br/>Failed to void UPS Capital Insurance: %s") % (insurance_result['error_message']))
                    self.message_post(body=log_message)
                elif insurance_result['result'] == 'SUCCESS':
                    self.update({
                        'capital_insurance_quote_id': False,
                        'capital_insurance_premium_amount': False
                    })
                    log_message = (_("UPS Capital Insurance for shipping option 1 has been voided."))
                    self.message_post(body=log_message)

        if self.is_void_second_label and second_fedex_service_type in ['GROUND_HOME_DELIVERY', 'FEDEX_GROUND']:
            if not self.second_capital_insurance_quote_id:
                log_message = (_("Shipping Option 2<br/>Failed to void UPS Capital Insurance: Missing Insurance Quote ID!"))
                self.message_post(body=log_message)
            else:
                second_insurance_result = insurance_request.void_insurance_quote(self.second_capital_insurance_quote_id, second_carrier_tracking_ref)
                if second_insurance_result['result'] == 'ERROR':
                    log_message = (_("Shipping Option 2<br/>Failed to void UPS Capital Insurance: %s") % (second_insurance_result['error_message']))
                    self.message_post(body=log_message)
                elif second_insurance_result['result'] == 'SUCCESS':
                    self.update({
                        'second_capital_insurance_quote_id': False,
                        'second_capital_insurance_premium_amount': False
                    })
                    log_message = (_("UPS Capital Insurance for shipping option 2 has been voided."))
                    self.message_post(body=log_message)

        return result
