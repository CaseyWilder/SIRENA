from odoo import models
from odoo.tools import pdf


class IrActionsReport(models.Model):
    _inherit = 'ir.actions.report'

    def _render_qweb_pdf(self, res_ids=None, data=None):
        """
        Inherit to handle special case for Payroll: Print Check + Paystub.

        * Original idea: pass context to report_action() in payroll_payslip.do_print_check(), then check it here
            report_action() -> action_manager_report.js -> report_download() -> report_routes() -> _render_qweb_pdf()
        But all contexts are lost after passing to action_manager_report.js -> Another way: Use param `data` in report_action() instead:
            if self._context.get('paystub', False):
                ...
                return report_id.report_action(self, data=data_ctx)

        * Issue: Odoo splits `docids` from param `data` (url) in report_download().
        But if data!=None in report_action(), format of url will be changed -> docids=None -> res_ids=None in _render_qweb_pdf()
        -> Nothing to render!!
        That's why we must give one more param 'docids', to use as res_ids:
                data_ctx = {'options': {'check_paystub': True, 'docids': self.ids}}

        :param res_ids:
        :param data:
        :return: (pdf file, 'pdf')
        """
        if (
                self and self[0].model == 'payroll.payslip' and
                isinstance(data, dict) and
                isinstance(data.get('options', False), dict) and
                data['options'].get('check_paystub', False) and
                isinstance(data['options'].get('docids', False), list)
        ):
            pdf_files = []
            paystub_report_id = self.env['payroll.payslip']._get_separated_stub_template()

            for res_id in data['options']['docids']:
                check, check_type = self._render_qweb_pdf(res_ids=[res_id])
                paystub, paystub_type = paystub_report_id._render_qweb_pdf(res_ids=[res_id])
                pdf_files.append(check)
                pdf_files.append(paystub)

            return pdf.merge_pdf(pdf_files), 'pdf'

        return super()._render_qweb_pdf(res_ids, data)
