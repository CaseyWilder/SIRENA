from odoo import api, fields, models
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT as DF
from datetime import date


class QuarterTaxReport(models.Model):
    _inherit = 'quarter.tax.report'

    def update_941_info(self):
        """
        Override to exclude contractor's compensations from the report
        """
        super(QuarterTaxReport, self).update_941_info()

        for record in self:
            company_id = self.company_id.id
            domain = [
                ('pay_date', '>=', date(int(record.year), 1, 1).strftime(DF)),
                ('pay_date', '<=', date(int(record.year), 12, 31).strftime(DF)),
                ('quarter', '=', record.quarter),
                ('company_id', '=', company_id),
                ('state', 'in', ['done'])
            ]
            pay_period_ids = self.env['pay.period'].search(domain)
            payslip_ids = pay_period_ids.mapped('payslip_ids')
            contractor_payslip_ids = payslip_ids.filtered(lambda r: r.employee_type == 'contractor')
            if not contractor_payslip_ids:
                continue
            normal_payslip_ids = payslip_ids - contractor_payslip_ids
            contractor_employee_ids = contractor_payslip_ids.mapped('employee_id')
            normal_employee_ids = normal_payslip_ids.mapped('employee_id')
            # Do not count employees which have only contractor payslips in 1. Number of Employees
            employee_ids = contractor_employee_ids - normal_employee_ids

            record.write({
                'no_employees': record.no_employees - len(employee_ids),
                'total_compensation': record.total_compensation - sum(contractor_payslip_ids.mapped('gross_pay'))
            })
