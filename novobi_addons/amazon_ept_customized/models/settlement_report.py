import base64
import csv
import logging
from datetime import datetime
from io import StringIO
from odoo import models, fields, api, _

_logger = logging.getLogger(__name__)


class SettlementReportEpt(models.Model):

    _inherit = "settlement.report.ept"

    def prepare_attachments(self, data, marketplace, start_date, end_date, currency_rec):
        """
        SRN-69
        Inherit: set Seller and Instance to settlement report
        """
        super(SettlementReportEpt, self).prepare_attachments(data, marketplace, start_date, end_date, currency_rec)

        if not self.instance_id:
            marketplace_id = self.env['amazon.marketplace.ept'].search([('name', '=', marketplace)])
            if marketplace_id:
                instance_id = self.env['amazon.instance.ept'].sudo().search([('marketplace_id', 'in', marketplace_id.ids)])
                if instance_id:
                    self.write({
                        'instance_id': instance_id[0].id,
                        'seller_id': instance_id[0].seller_id.id
                    })

