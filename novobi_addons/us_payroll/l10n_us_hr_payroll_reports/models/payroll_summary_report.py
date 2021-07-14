from odoo import models, api, fields, _


class PayrollSummaryReport(models.AbstractModel):
    _name = "payroll.summary.report"
    _description = "Payroll Summary Report"
    _inherit = 'account.report'

    filter_date = {'mode': 'range', 'date_from': '', 'date_to': '', 'filter': 'this_year'}

    STRUCTURE_LINES = [{'name': 'Compensations',
                        'slip_model': 'payslip_compensation',
                        'slip_field': 'compensation_id',
                        'roll_model': 'payroll_compensation'},

                       {'name': 'Taxes Withheld',
                        'slip_model': 'payslip_tax',
                        'slip_field': 'payroll_tax_id',
                        'roll_model': 'payroll_tax',
                        'amount_field': 'tax_amt',
                        'extra_where': 'AND ROLL.is_er_tax = FALSE'},

                       {'name': 'Deductions from Net Pay',
                        'slip_model': 'payslip_deduction',
                        'slip_field': 'deduction_id',
                        'roll_model': 'payroll_deduction',
                        },

                       {'name': 'Net Pay'},

                       {'name': 'Company Taxes',
                        'slip_model': 'payslip_tax',
                        'slip_field': 'payroll_tax_id',
                        'roll_model': 'payroll_tax',
                        'amount_field': 'tax_amt',
                        'extra_where': 'AND ROLL.is_er_tax = TRUE'},

                       {'name': 'Company Contribution',
                        'slip_model': 'payslip_deduction',
                        'slip_field': 'deduction_id',
                        'roll_model': 'payroll_deduction',
                        'amount_field': 'er_dollar_amt',
                        },
                       ]

    @api.model
    def _get_report_name(self):
        return _('Payroll Summary')

    def _get_columns_name(self, options):
        return [
            {},
            {'name': _('Amount'), 'class': 'number'},
        ]

    def build_where_clause(self, extra_where):
        where_clause = """
            WHERE state in ('done') 
            AND (SLIP.pay_date >= %s) AND (SLIP.pay_date <= %s)
            AND SLIP.company_id IN %s
            {}
        """.format(extra_where)
        return where_clause

    def _get_data_lines(self, options, structure):
        cr = self.env.cr

        date_from = options['date']['date_from']
        date_to = options['date']['date_to']
        company_ids = self.env.context.get('company_ids', (self.env.company.id,))

        sql_params = [date_from, date_to, tuple(company_ids)]

        # SQL
        slip_model = structure.get('slip_model', False)
        roll_model = structure.get('roll_model', False)
        extra_where = structure.get('extra_where', "")
        amount_field = structure.get('amount_field', "amount")

        select_clause = "SELECT SLIP.name as column_name, SUM(SLIP.{}) as amount".format(amount_field)
        from_clause = "FROM {} as SLIP".format(slip_model)
        where_clause = self.build_where_clause(extra_where)

        # Special treatment for NET PAY
        if structure.get('name', False) == 'Net Pay':
            query = """
            SELECT 'Net Pay' as column_name,
                SUM(SLIP.net_pay) as amount 
            FROM payroll_payslip as SLIP 
            {}
             """.format(where_clause)

            cr.execute(query, sql_params)
        else:
            if roll_model:
                # Need to join other table to get name
                slip_field = structure.get('slip_field', False)

                select_clause = "SELECT ROLL.name as column_name, SUM(SLIP.{}) as amount".format(amount_field)
                from_clause = """FROM {} as SLIP 
                    JOIN {} as ROLL 
                    ON SLIP.{} = ROLL.id""".format(slip_model, roll_model, slip_field)

            query = """
                {} {} {}
                GROUP BY column_name
                HAVING SUM(SLIP.{}) > 0
                ORDER BY column_name;
            """.format(select_clause, from_clause, where_clause, amount_field)

            cr.execute(query, sql_params)

        data = cr.dictfetchall()
        return data

    @api.model
    def _get_lines(self, options, line_id=None):
        lines = []
        unfold_all = False  # fold by default
        company_cost = 0

        for structure in self.STRUCTURE_LINES:
            structure_name = structure['name']

            if line_id and line_id != structure_name:  # Expand a section
                continue

            data = self._get_data_lines(options, structure)
            children_lines = []

            # Load children lines, we put in here first since we want to calculate the total
            total = 0
            for line in data:
                amount = line.get('amount', 0) if line.get('amount', 0) else 0
                total += amount
                vals = {
                    'id': line['column_name'],
                    'parent_id': structure_name,
                    'name': line['column_name'],
                    'level': 4,
                    'columns': [{'name': self.format_value(amount)}],
                }
                children_lines.append(vals)
            # Total line for each section
            children_lines.append({
                'id': "Total {}".format(structure['name']),
                'parent_id': structure_name,
                'name': "Total {}".format(structure['name']),
                'level': 2,
                'class': 'o_account_reports_totals_below_sections',
                'columns': [{'name': self.format_value(total)}],
            })

            # Company Cost = Gross Pay + Company Tax + Company Contribution
            if structure_name in ['Compensations', 'Company Taxes', 'Company Contribution']:
                company_cost += total

            # Special treatment for NET PAY
            if structure_name == 'Net Pay':
                lines.append({
                    'id': structure_name,
                    'name': structure_name,
                    'level': 1,
                    'columns': [{'name': self.format_value(total)}],
                })

                # Add an empty line after the total to make a space between two currencies
                lines.append({
                    'id': '',
                    'name': '',
                    'class': ' o_account_reports_level0_no_border  ',
                    'unfoldable': False,
                    'level': 0,
                    'columns': [],
                })
                continue

            # The Label line
            lines.append({
                'id': structure_name,
                'name': structure_name,
                'level': 2,
                'unfoldable': True,
                'unfolded': structure_name in options.get('unfolded_lines') or unfold_all,
                'columns': [{'name': self.format_value(total)}],
            })

            # Expand a section, load all children lines
            if structure_name in options.get('unfolded_lines') or unfold_all:
                lines.extend(children_lines)

        # Company Cost
        if not line_id:
            lines.append({
                'id': 'Company Cost',
                'name': _('Company Cost'),
                'level': 0,
                'class': 'o_account_reports_totals_below_sections',
                'columns': [{'name': self.format_value(company_cost)}],
            })

        return lines
