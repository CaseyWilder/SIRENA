from odoo import http
from odoo.http import request
from odoo.addons.web.controllers.main import ExcelExport, content_disposition
import json


class USPayrollExport(ExcelExport):

    @http.route('/period_export_payslip_compensation/<string:str_ids>', type='http', auth='user')
    def get_period_payslip_compensation(self, str_ids, **kwargs):
        """
        Get historical Compensation data of all Payslips in a Period.
        :param str_ids: string of payslips id with format id1-id2-id3...
        :param kwargs:
        :return:
        """
        token = 'dummy-because-api-expects-one'

        # Avoid using this way because wizard.payslip_ids = False (but wizard.period_id still exists).
        # Not sure why this not works on v13, 14
        # wizard_id = request.env['export.historical.data.wizard'].sudo().browse(id)
        # payslip_ids = wizard_id.payslip_ids

        int_ids = map(int, str_ids.split('-'))
        payslip_ids = request.env['payroll.payslip'].sudo().browse(int_ids)
        compensation_ids = payslip_ids\
            .mapped('compensation_ids')\
            .filtered(lambda r: r.compensation_id in r.payslip_id.wizard_compensation_ids)

        data = {
            'model': 'payslip.compensation',
            'fields': [
                {"name": "id",                  "label": "External ID"},
                {"name": "payslip_id",          "label": "Payslip"},
                {"name": "employee_id",         "label": "Employee"},
                {"name": "compensation_id",     "label": "Compensation"},
                {"name": "label",               "label": "Label on paycheck"},
                {"name": "amount",              "label": "Amount"},
            ],
            'ids': compensation_ids.ids,
            'domain': [('id', 'in', compensation_ids.ids)],
            'context': request.env.context,
            'import_compat': False
        }

        return self.index(json.dumps(data), token)

    @http.route('/period_export_payslip_deduction/<string:str_ids>', type='http', auth='user')
    def get_period_payslip_deduction(self, str_ids, **kwargs):
        """
        Get historical Deduction data of all Payslips in a Period.
        :param str_ids: string of payslips id with format id1-id2-id3...
        :param kwargs:
        :return:
        """
        token = 'dummy-because-api-expects-one'

        # Avoid using this way because wizard.payslip_ids = False (but wizard.period_id still exists).
        # Not sure why this not works on v13, 14
        # wizard_id = request.env['export.historical.data.wizard'].sudo().browse(id)
        # payslip_ids = wizard_id.payslip_ids

        int_ids = map(int, str_ids.split('-'))
        payslip_ids = request.env['payroll.payslip'].sudo().browse(int_ids)
        deduction_ids = payslip_ids \
            .mapped('deduction_ids') \
            .filtered(lambda r: r.deduction_id in r.payslip_id.wizard_deduction_ids)

        data = {
            'model': 'payslip.deduction',
            'fields': [
                {"name": "id",                          "label": "External ID"},
                {"name": "employee_id",                 "label": "Employee"},
                {"name": "deduction_id",                "label": "Deduction"},
                {"name": "label",                       "label": "Label on paycheck"},
                {"name": "er_amount",                   "label": "Company Deduction Amount"},
                {"name": "ee_amount",                   "label": "Employee Deduction Amount"},
            ],
            'ids': deduction_ids.ids,
            'domain': [('id', 'in', deduction_ids.ids)],
            'context': request.env.context,
            'import_compat': False
        }

        return self.index(json.dumps(data), token)

    @http.route('/period_export_payslip_tax/<int:id>', type='http', auth='user')
    def get_period_payslip_tax(self, id, **kwargs):
        """
        Get historical Tax data of all Payslips in a Period.
        :param id: period_id
        :param kwargs:
        :return:
        """
        token = 'dummy-because-api-expects-one'
        period_id = request.env['pay.period'].sudo().browse(id)
        tax_ids = period_id.payslip_ids.mapped('tax_ids')

        data = {
            'model': 'payslip.tax',
            'fields': [
                {"name": "id", "label": "External ID"},
                {"name": "payslip_id", "label": "Payslip"},
                {"name": "employee_id", "label": "Employee"},
                {"name": "payroll_tax_id", "label": "Payroll Tax"},
                {"name": "adjusted_gross", "label": "Wage Base"},
                {"name": "tax_amt", "label": "Tax Amount"},
            ],
            'ids': tax_ids.ids,
            'domain': [('id', 'in', tax_ids.ids)],
            'context': request.env.context,
            'import_compat': False
        }

        return self.index(json.dumps(data), token)

    @http.route('/period_print_ach_file/<int:id>', type='http', auth='user')
    def get_period_ach_file(self, id, **kwargs):
        """
        Generate ACH file.
        :param id: period_id
        :param kwargs:
        :return:
        """
        period_id = request.env['pay.period'].sudo().browse(id)
        ach_file = period_id.generate_ach_file()

        content = ach_file.render_to_string()

        return request.make_response(content, headers=[
            ('Content-Disposition', content_disposition('ACH_{}.txt'.format(period_id.name))),
            ('Content-Type', 'text/plain'),
            ('Content-Length', len(content)),
        ])
