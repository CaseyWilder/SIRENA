from odoo import http
from odoo.http import request
from odoo.addons.web.controllers.main import ExcelExport
import json


class USPayrollExport(ExcelExport):

    @http.route('/payroll_direct_deposit/<int:id>', type='http', auth='user')
    def get_payroll_direct_deposit(self, id, **kw):
        token = 'dummy-because-api-expects-one'
        pay_period = request.env['pay.period'].sudo().browse(id)
        payslip = pay_period.payslip_ids.filtered(lambda x: x.payment_method == 'deposit')

        data = {
            "model": "payroll.payslip",
            "fields": [
                {"name": "employee_code", "label": "ID"},
                {"name": "employee_id/name", "label": "Full Name"},
                {"name": "pay_period_id/pay_date", "label": "Pay Date"},
                {"name": "net_pay", "label": "Net Amount"},
            ],
            "ids": payslip.ids,
            "domain": [('id', 'in', payslip.ids)],
            "context": request.env.context,
            "import_compat": False
        }

        return self.index(json.dumps(data), token)
