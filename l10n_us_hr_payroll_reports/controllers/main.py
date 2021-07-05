from odoo import http
from odoo.http import request
from odoo.addons.web.controllers.main import ExcelExport
import json


class USPayrollExport(ExcelExport):

    @http.route('/semiweekly_tax_export/<int:id>', type='http', auth='user')
    def get_semiweekly_tax_report(self, id, **kw):
        token = 'dummy-because-api-expects-one'
        report = request.env['semiweekly.tax.report'].sudo().browse(id)

        data = {
            "model": "semiweekly.tax.report",
            "fields": [
                {"name": "name", "label": "Name"},
                {"name": "month_1", "label": "Tax Liability Month 1"},
                {"name": "month_2", "label": "Tax Liability Month 2"},
                {"name": "month_3", "label": "Tax Liability Month 3"},
                {"name": "total_tax_liability", "label": "Total Tax Liability"},

                {"name": "line_ids/name", "label": "Month"},
                {"name": "line_ids/pay_date", "label": "Pay Date"},
                {"name": "line_ids/amount", "label": "Amount"},
            ],
            "ids": report.id,
            "domain": [('id', '=', report.id)],
            "context": request.env.context,
            "import_compat": False
        }

        return self.index(json.dumps(data), token)
