from odoo import models, fields, api, _


class ResPartner(models.Model):

    _inherit = "res.partner"

    def woo_create_contact_customer(self, vals, instance=False):
        """
        Inherit: add company to customer
        """
        partner = super(ResPartner, self).woo_create_contact_customer(vals, instance)
        if partner:
            partner.write({'company_id': instance.company_id.id})
        return partner

    def woo_prepare_partner_vals(self, vals, instance):
        """
        Inherit: add company to partner vals
        """
        res = super(ResPartner, self).woo_prepare_partner_vals(vals, instance)
        res.update({'company_id': instance.company_id.id})
        return res
