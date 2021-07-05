from odoo.addons.web.controllers.main import ReportController
from odoo.http import route


class PdfPreviewController(ReportController):

    @route(['/report/preview'], type='http', auth="user")
    def report_download(self, data, token, context=None):
        result = super().report_download(data, token)
        result.headers['Content-Disposition'] = result.headers['Content-Disposition'].replace('attachment', 'inline')
        return result
