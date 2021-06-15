# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import pdf


class IrActionsReport(models.Model):
    _inherit = 'ir.actions.report'

    def render_qweb_text(self, res_ids=None, data=None):
        report_shipping_label = self.env.ref('novobi_shipping_account.action_report_shipping_label')
        # Force shipping labels to be printed at the central place
        if self == report_shipping_label:
            return self.render_qweb_pdf(res_ids, data)
        return super(IrActionsReport, self).render_qweb_text(res_ids, data)

    def render_qweb_pdf(self, res_ids=None, data=None):
        """
        This method is not just for printing PDF but a central place for many other formats
        """
        def print_label():
            pickings = self.env[self.model].browse(res_ids)
            common_ext = None
            result = list()
            for p in pickings:
                res = p.get_carrier_label_document()
                if not res:
                    raise UserError(_('Unable to print label.'))
                ext, binary = res
                if common_ext is None:
                    common_ext = ext.lower()
                if common_ext != ext.lower():
                    raise UserError(_('Inconsistent label types'))
                result.append(binary)
            return common_ext, result

        report_packing_slip = self.env.ref('novobi_shipping_account.action_report_packing_slip')
        report_shipping_label = self.env.ref('novobi_shipping_account.action_report_shipping_label')
        report_label_packing_slip = self.env.ref('novobi_shipping_account.action_report_shipping_label_packing_slip')

        if len(self) == 1 and self == report_packing_slip:
            this = self.with_context(report_packing_slip=True)
            return super(IrActionsReport, this).render_qweb_pdf(res_ids, data)
        if len(self) == 1 and self == report_shipping_label:
            label_ext, labels = print_label()
            if len(labels) == 1:
                return labels[0], label_ext
            elif label_ext == 'pdf':
                return pdf.merge_pdf(labels), label_ext
            elif label_ext == 'zpl':
                return b''.join(labels), label_ext
            else:
                # Unsupported format
                return labels[0], label_ext
        if len(self) == 1 and len(res_ids) == 1 and self == report_label_packing_slip:
            company = self.env.company
            if company.shipping_label_options == 'wo_packing':
                label_ext, labels = print_label()
                # 1-label Assumption
                return labels[0], label_ext
            else:
                packing_slip_binary, t = report_packing_slip.render_qweb_pdf(res_ids, data)
                shipping_label_binary, t = report_shipping_label.render_qweb_pdf(res_ids, data)
                if t.lower() != 'pdf':
                    raise UserError(_('Unsupported label format!'))
                return pdf.merge_pdf([packing_slip_binary, shipping_label_binary]), 'pdf'
        return super(IrActionsReport, self).render_qweb_pdf(res_ids, data)

    @api.model
    def get_paperformat(self):
        if self.env.context.get('report_packing_slip'):
            return self.env.company.packing_slip_size
        return super(IrActionsReport, self).get_paperformat()
