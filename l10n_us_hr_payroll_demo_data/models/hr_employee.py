import random
from datetime import datetime, timedelta
from odoo import api, fields, models, _


class Employee(models.Model):
    _inherit = 'hr.employee'

    # ============== INIT DATA =========================
    @api.model
    def generate_demo_data(self):
        company = self.env.company
        # Delete all attendance records cause we're gonna create it later
        Attendance = self.env['hr.attendance']
        Attendance.search([]).unlink()

        # Get all current employee
        employees = self.env['hr.employee'].search([('company_id', '=', company.id)])

        # Random dependant
        address_data = [
            {'city': 'Newark',      'zip': '19702'},
            {'city': 'Newark',      'zip': '19711'},
            {'city': 'Newark',      'zip': '19715'},
            {'city': 'Wilmington',  'zip': '19896'},
            {'city': 'Wilmington',  'zip': '19891'}
        ]
        salary_data = [
            {'employee_type': 'salary', 'salary_amount': 1000,  'salary_period': '52', 'calculate_salary_by': 'hour'},
            {'employee_type': 'salary', 'salary_amount': 1300,  'salary_period': '52', 'calculate_salary_by': 'paycheck'},
            {'employee_type': 'salary', 'salary_amount': 900,   'salary_period': '52', 'calculate_salary_by': 'paycheck'},
            {'employee_type': 'hourly', 'salary_amount': 15},
            {'employee_type': 'hourly', 'salary_amount': 20}
        ]
        payment_data = [
            {'payment_method': 'check'},
            {'payment_method': 'deposit', 'split_paychecks_type': 'percentage',
             'payment_account_ids': [(0, 0, {'account_name': 'Bank Account 1', 'routing_number': '121044055', 'account_number': '99999999', 'amount_percentage': 45}),
                                     (0, 0, {'account_name': 'Bank Account 2', 'routing_number': '121425742', 'account_number': '88888888', 'amount_percentage': 55})]}
        ]
        compensation_data = [
            {'employee_compensation_ids': [(0, 0, {'compensation_id': self.env.ref('l10n_us_hr_payroll.payroll_compensation_2').id, 'label': 'Bonus', 'amount': 20})]},
            {'employee_compensation_ids': [(0, 0, {'compensation_id': self.env.ref('l10n_us_hr_payroll.payroll_compensation_10').id, 'label': 'Tips', 'amount': 10})]},
            {'employee_compensation_ids': [(0, 0, {'compensation_id': self.env.ref('l10n_us_hr_payroll.payroll_compensation_2').id, 'label': 'Bonus', 'amount': 10}),
                                           (0, 0, {'compensation_id': self.env.ref('l10n_us_hr_payroll.payroll_compensation_10').id, 'label': 'Tips', 'amount': 5})]},
            {}
        ]

        deduction_data = [
            {'employee_deduction_ids': [(0, 0, {'deduction_policy_id': self.env.ref('l10n_us_hr_payroll_demo_data.policy_401').id,
                                                'deduction_id': self.env.ref('l10n_us_hr_payroll.payroll_deduction_1').id,
                                                'label': '401k',
                                                'has_company_contribution': True,
                                                'ee_amount_type': 'fixed',
                                                'ee_amount': 50,
                                                'er_amount_type': 'fixed',
                                                'er_amount': 20}),
                                        (0, 0, {'deduction_policy_id': self.env.ref('l10n_us_hr_payroll_demo_data.policy_insurance').id,
                                                'deduction_id': self.env.ref('l10n_us_hr_payroll.payroll_deduction_441').id,
                                                'label': 'Medical Insurance',
                                                'has_company_contribution': True,
                                                'ee_amount_type': 'fixed',
                                                'ee_amount': 40,
                                                'er_amount_type': 'match',
                                                'er_amount': 50})]},
            {'employee_deduction_ids': [(0, 0, {'deduction_policy_id': self.env.ref('l10n_us_hr_payroll_demo_data.policy_401').id,
                                                'deduction_id': self.env.ref('l10n_us_hr_payroll.payroll_deduction_1').id,
                                                'label': '401k',
                                                'has_company_contribution': True,
                                                'ee_amount_type': 'fixed',
                                                'ee_amount': 45,
                                                'er_amount_type': 'fixed',
                                                'er_amount': 20}),
                                        (0, 0, {'deduction_policy_id': self.env.ref('l10n_us_hr_payroll_demo_data.policy_insurance').id,
                                                'deduction_id': self.env.ref('l10n_us_hr_payroll.payroll_deduction_441').id,
                                                'label': 'Medical Insurance',
                                                'has_company_contribution': True,
                                                'ee_amount_type': 'fixed',
                                                'ee_amount': 30,
                                                'er_amount_type': 'match',
                                                'er_amount': 50})]},
            {'employee_deduction_ids': [(0, 0, {'deduction_policy_id': self.env.ref('l10n_us_hr_payroll_demo_data.policy_401').id,
                                                'deduction_id': self.env.ref('l10n_us_hr_payroll.payroll_deduction_1').id,
                                                'label': '401k',
                                                'has_company_contribution': True,
                                                'ee_amount_type': 'fixed',
                                                'ee_amount': 20,
                                                'er_amount_type': 'fixed',
                                                'er_amount': 20})]},
            {'employee_deduction_ids': [(0, 0, {'deduction_policy_id': self.env.ref('l10n_us_hr_payroll_demo_data.policy_insurance').id,
                                                'deduction_id': self.env.ref('l10n_us_hr_payroll.payroll_deduction_441').id,
                                                'label': 'Medical Insurance',
                                                'has_company_contribution': True,
                                                'ee_amount_type': 'fixed',
                                                'ee_amount': 60,
                                                'er_amount_type': 'match',
                                                'er_amount': 50})]}
        ]

        filing_status_data = []
        status_ids = self.env['filing.status'].search([('vertex_id', 'in', ['1', '2'])])  # Single & Married
        if status_ids and len(status_ids) == 2:
            filing_status_data = [
                {'fed_filing_status_id': status_ids[0].id, 'work_filing_status_id': status_ids[0].id},
                {'fed_filing_status_id': status_ids[1].id, 'work_filing_status_id': status_ids[1].id}
            ]

        data_list = [address_data, salary_data, payment_data, compensation_data, deduction_data, filing_status_data]

        for employee in employees:
            value = {
                'work_city': 'Newark',
                'work_state_id': self.env.ref('base.state_us_8').id,
                'work_zip': '19702',
                'work_country_id': self.env.ref('base.us').id,
                'state_id': self.env.ref('base.state_us_8').id,
                'country_id': self.env.ref('base.us').id,
            }

            for data in data_list:
                value = self.update_demo_data_dict(data, value)

            employee.with_context(from_partner='1').write(value)

            # Create Attendance
            for i in range(1, 6):
                hour = random.randrange(30, 50)
                check_in = datetime.today() - timedelta(weeks=i, days=3)
                check_out = check_in + timedelta(hours=hour)

                Attendance.create({
                    'employee_id': employee.id,
                    'check_in': check_in,
                    'check_out': check_out
                })

    def update_demo_data_dict(self, data, value):
        index = random.randrange(len(data))
        value.update(data[index])
        return value
