# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.


"""
Main Model for Vat Configuration.
"""
import logging
from odoo import api, fields, models

_logger = logging.getLogger("Amazon")


class VatConfigLineEpt(models.Model):
    """
    For Setting VAT number for Country.
    @author: Maulik Barad on Date 11-Jan-2020.
    """
    _name = "vat.config.line.ept"
    _description = "VAT Configuration Line EPT"

    def _get_country_domain(self):
        """
        Creates domain to only allow to select company from allowed companies in switchboard.
        @author: Maulik Barad on Date 11-Jan-2020.
        """
        country_list = []
        europe_group = self.env.ref("base.europe", raise_if_not_found=False)
        uk_ref = self.env.ref("base.uk", raise_if_not_found=False)
        if europe_group:
            country_list = europe_group.country_ids.ids
        if uk_ref:
            country_list += uk_ref.ids
        return [("id", "in", country_list)]

    vat_config_id = fields.Many2one("vat.config.ept", ondelete="cascade")
    vat = fields.Char("VAT Number")
    country_id = fields.Many2one("res.country", domain=_get_country_domain)

    _sql_constraints = [
        ("unique_country_vat_config", "UNIQUE(vat_config_id,country_id)",
         "VAT configuration is already added for the country.")]

    @api.model
    def create(self, values):
        """
        Inherited the create method for updating the VAT number and creating Fiscal positions.
        @author: Maulik Barad on Date 13-Jan-2020.
        @author: Twinkal Chandarana on date 12-FEB-2021
        MOD : Create an VCS FPOS based on VAT number configurations.
        """
        result = super(VatConfigLineEpt, self).create(values)
        warehouse_obj = self.env["stock.warehouse"]

        data = {"company_id": result.vat_config_id.company_id.id,
                "vat_config_id": values["vat_config_id"], "is_amazon_fpos": True}

        country_id = result.country_id
        excluded_vat_registered_europe_group = self.env.ref("amazon_ept.excluded_vat_registered_europe")
        if country_id.id in excluded_vat_registered_europe_group.country_ids.ids:
            excluded_vat_registered_europe_group.country_ids = [(3, country_id.id, 0)]
            _logger.info("COUNTRY REMOVED FROM THE EUROPE GROUP ")

        # Updating the VAT number into warehouse's partner of the same country.
        warehouses = warehouse_obj.search([("company_id", "=", data["company_id"])])
        if warehouses:
            warehouse_partners = warehouses.partner_id.filtered(lambda x: x.country_id.id == country_id.id)
            warehouse_partners.write({"vat": values["vat"]})
            _logger.info( \
                    "VAT Number Updated OF Warehouse's Partner Which Belongs To Country %s." % (country_id.id))

        # Creating Amazon Fiscal positions.
        self.create_amazon_fpos_ept(data, country_id)

        return result

    def create_amazon_fpos_ept(self, data, country_id):
        """
        Create Fiscal Positions Automatically as per VAT number Configurations.
        For Ex. France VAT
            - Deliver to France(B2C)
            - VCS - Deliver to France(VAT Required)(B2B)
            - Deliver from France to Europe(Exclude VAT registered country)(B2C)
            - VCS - Deliver from France to Europe(VAT Required)(B2B)
            - VCS - Deliver from France to Outside Europe (B2C)
            - VCS - Deliver from France to Outside Europe (VAT Required)(B2B)


        """
        fiscal_position_obj = self.env["account.fiscal.position"]
        excluded_vat_registered_europe_group = self.env.ref("amazon_ept.excluded_vat_registered_europe")
        europe_group = self.env.ref('base.europe', raise_if_not_found=False)
        country_name = country_id.name

        # Delivered Country to Country
        existing_fiscal_position = fiscal_position_obj.search( [("company_id", "=", data["company_id"]),
                                                                ("country_id", "=", country_id.id)], limit=1)
        if not existing_fiscal_position:
            data.update({'name': "Deliver to %s" % country_name,
                         'country_id': country_id.id})
            fiscal_position_obj.create(data)
            _logger.info("Fiscal Position Created For Country %s." % country_name)
        elif not existing_fiscal_position.is_amazon_fpos:
            existing_fiscal_position.is_amazon_fpos = True

        # VCS - Vat Required - Delivered Country to Country
        vat_fiscal_position = fiscal_position_obj.search([("company_id", "=", data["company_id"]),
                                                          ("country_id", "=", country_id.id),
                                                          ('vat_required', '=', True)], limit=1)
        if not vat_fiscal_position:
            data.update({'name': "VCS - Deliver to %s" % country_name,
                         'country_id': country_id.id, 'vat_required': True})
            fiscal_position_obj.create(data)
            _logger.info("VCS - Fiscal Position Created For Country %s." % country_name)
        elif not vat_fiscal_position.is_amazon_fpos:
            vat_fiscal_position.is_amazon_fpos = True

        # VAT Required False - Delivered Country to EU(Exclude VAT registered country)
        existing_excluded_fiscal_position = fiscal_position_obj.search(
            [("company_id", "=", data["company_id"]), ("origin_country_ept", "=", country_id.id),
             ('vat_required', '=', False), ("country_group_id", "=", excluded_vat_registered_europe_group.id if
            excluded_vat_registered_europe_group else False)], limit=1)
        if not existing_excluded_fiscal_position:
            data.update({"name": "Deliver from %s to Europe(Exclude VAT registered country)" % country_name,
                         "origin_country_ept": country_id.id, 'vat_required': False,
                         "country_group_id": excluded_vat_registered_europe_group.id if
                         excluded_vat_registered_europe_group else False})
            if 'country_id' in data.keys():
                del data['country_id']
            fiscal_position_obj.create(data)
            _logger.info("Fiscal Position Created From %s To Excluded Country Group." % country_name)
        elif not existing_excluded_fiscal_position.is_amazon_fpos:
            existing_excluded_fiscal_position.is_amazon_fpos = True

        # VAT REquired - VCS Delivered Country to EU
        existing_europe_vat_fpos = fiscal_position_obj.search([
            ("company_id", "=", data["company_id"]), ('vat_required', '=', True),
            ("origin_country_ept", "=", country_id.id),
            ("country_group_id", "=", europe_group.id if europe_group else False)], limit=1)
        if not existing_europe_vat_fpos:
            data.update({"name": "VCS - Deliver from %s to Europe" % country_name,
                         "origin_country_ept": country_id.id, "vat_required": True,
                         "country_group_id": europe_group.id if europe_group else False})
            fiscal_position_obj.create(data)
            _logger.info("VCS - Fiscal Position Created From %s To Europe Country Group." % country_name)
        elif not existing_europe_vat_fpos.is_amazon_fpos:
            existing_europe_vat_fpos.is_amazon_fpos = True

        # VCS - Delivered Country to Outside EU
        outside_eu_fiscal_position = fiscal_position_obj.search([("company_id", "=", data["company_id"]),
                                                                 ("origin_country_ept", "=", country_id.id),
                                                                 ('country_group_id', '=', False)], limit=1)
        if not outside_eu_fiscal_position:
            data.update({"name": "VCS - Deliver from %s to Outside Europe" % country_name,
                         'origin_country_ept': country_id.id, "vat_required": False})
            if 'country_group_id' in data.keys():
                del data['country_group_id']
            fiscal_position_obj.create(data)
            _logger.info("VCS - Fiscal Position Created From %s To Outside EU." % country_name)
        elif not outside_eu_fiscal_position.is_amazon_fpos:
            outside_eu_fiscal_position.is_amazon_fpos = True

        # VCS - Delivered Country to Outside EU(VAT Required)
        vcs_outside_eu_fiscal_position = fiscal_position_obj.search([("company_id", "=", data["company_id"]),
                                                                      ("origin_country_ept", "=", country_id.id),
                                                                      ('vat_required', '=', True),
                                                                      ('country_group_id', '=', False)], limit=1)
        if not vcs_outside_eu_fiscal_position:
            data.update({"name": "VCS - Deliver from %s to Outside Europe(VAT Required)" % country_name,
                         'origin_country_ept': country_id.id, "vat_required": True})
            if 'country_group_id' in data.keys():
                del data['country_group_id']
            fiscal_position_obj.create(data)
            _logger.info("VCS - Fiscal Position Created From %s To Outside EU(VAT Required)." % country_name)
        elif not vcs_outside_eu_fiscal_position.is_amazon_fpos:
            vcs_outside_eu_fiscal_position.is_amazon_fpos = True

        return True
