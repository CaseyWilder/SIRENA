from odoo import api, fields, models
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT as DF
from datetime import date


class WageTaxReport(models.Model):
    _inherit = 'wage.tax.report'

    def _get_contractor_box12_ded_info(self, company_id, employee_id):
        query = """
            SELECT ROLL.w2_code,
                SUM(amount) AS amount,
                deduction_id
            FROM payroll_payslip PSLIP 
                JOIN payslip_deduction SLIP ON PSLIP.id = SLIP.payslip_id
                JOIN payroll_deduction ROLL ON SLIP.deduction_id = ROLL.id
            WHERE ROLL.w2_code IS NOT NULL
                AND PSLIP.employee_type = 'contractor'
                AND DATE_PART('year', SLIP.pay_date) = {}
                AND SLIP.state IN ('done')
                AND SLIP.company_id = {}
                AND SLIP.employee_id = {}
            GROUP BY w2_code, deduction_id
        """.format(self.year, company_id, employee_id)

        return self._execute_sql_report(query)

    def _get_contractor_box12_comp_info(self, company_id, employee_id):
        query = """
            SELECT ROLL.w2_code,
                SUM(amount) AS amount,
                compensation_id
            FROM payroll_payslip PSLIP 
                JOIN payslip_compensation SLIP ON PSLIP.id = SLIP.payslip_id
                JOIN payroll_compensation ROLL ON SLIP.compensation_id = ROLL.id
            WHERE ROLL.w2_code IS NOT NULL
                AND PSLIP.employee_type = 'contractor'
                AND DATE_PART('year', SLIP.pay_date) = {}
                AND SLIP.state IN ('done')
                AND SLIP.company_id = {}
                AND SLIP.employee_id = {}
            GROUP BY w2_code, compensation_id
        """.format(self.year, company_id, employee_id)

        return self._execute_sql_report(query)

    def update_report_info(self):
        """
        Override to exclude contractor's compensations and deductions from the report
        """
        super(WageTaxReport, self).update_report_info()

        # Box 10 deductions
        dependent_care_reg = self.env.ref('l10n_us_hr_payroll.payroll_deduction_14')
        dependent_care_sup = self.env.ref('l10n_us_hr_payroll.payroll_deduction_15')

        for record in self:
            company_id = record.company_id.id
            employee_id = record.employee_id.id
            domain = [('pay_date', '>=', date(int(record.year), 1, 1).strftime(DF)),
                      ('pay_date', '<=', date(int(record.year), 12, 31).strftime(DF)),
                      ('company_id', '=', company_id),
                      ('employee_id', '=', employee_id),
                      ('employee_type', '=', 'contractor'),
                      ('state', 'in', ['done'])]

            payslip_ids = self.env['payroll.payslip'].search(domain)
            if not payslip_ids:
                continue
            payslip_deduction_ids = payslip_ids.mapped('deduction_ids')

            # Exclude 1. Wages, tips, and other compensation
            pre_deductions = payslip_deduction_ids.filtered('deduction_id.category_id')
            contractor_compensation = sum(payslip_ids.mapped('gross_pay')) - sum(pre_deductions.mapped('amount'))

            # Exclude 10. Dependent care benefits
            contractor_dependent_care = sum(payslip_deduction_ids.filtered(
                lambda x: x.deduction_id in [dependent_care_reg, dependent_care_sup]).mapped('amount'))

            # Exclude compensations/deductions from Box 12
            contractor_box12_data = record._get_contractor_box12_ded_info(company_id, employee_id)
            contractor_box12_data += record._get_contractor_box12_comp_info(company_id, employee_id)
            for data in contractor_box12_data:
                w2_code = data.get('w2_code', False)
                amount = data.get('amount', 0)
                deduction_id = data.get('deduction_id', False)
                compensation_id = data.get('compensation_id', False)
                box12_id = record.box12_ids.filtered(lambda r: r.w2_code == w2_code)
                box12_line_id = box12_id.line_ids.filtered(lambda r: (r.deduction_id and r.deduction_id.id == deduction_id)
                                                                     or (r.compensation_id and r.compensation_id.id == compensation_id))
                if box12_line_id.amount == amount:
                    box12_line_id.unlink()
                else:
                    box12_line_id.amount -= amount

                if not box12_id.line_ids:
                    box12_id.unlink()

            record.write({
                'total_compensation': record.total_compensation - contractor_compensation,
                'dependent_care': record.dependent_care - contractor_dependent_care
            })
