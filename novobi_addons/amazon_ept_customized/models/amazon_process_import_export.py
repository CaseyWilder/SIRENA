from odoo import models, fields, api, _


class AmazonProcessImportExport(models.TransientModel):

    _inherit = 'amazon.process.import.export'

    def prepare_fba_report_vals(self, list_of_wrapper, start_date, end_date, model_obj, sequence):
        """
        SRN-69
        Override: add sudo() when search for report_exist
        """
        odoo_report_ids = []
        if list_of_wrapper is None:
            return []

        for result in list_of_wrapper:
            reports = []
            if not isinstance(result.get('ReportInfo', []), list):
                reports.append(result.get('ReportInfo', []))
            else:
                reports = result.get('ReportInfo', [])
            for report in reports:
                request_id = report.get('ReportRequestId', {}).get('value', '')
                report_id = report.get('ReportId', {}).get('value', '')
                report_type = report.get('ReportType', {}).get('value', '')
                # changed part: add sudo()
                report_exist = model_obj.sudo().search(
                    ['|', ('report_request_id', '=', request_id), ('report_id', '=', report_id),
                     ('report_type', '=', report_type)])
                # end of changed part
                if report_exist:
                    report_exist = report_exist[0]
                    odoo_report_ids.append(report_exist.id)
                    continue
                vals = self.prepare_fba_report_vals_for_create(report_type, request_id, report_id,
                                                               start_date, end_date,
                                                               sequence)
                report_rec = model_obj.create(vals)
                report_rec.get_report()
                self._cr.commit()
                odoo_report_ids.append(report_rec.id)
        return odoo_report_ids