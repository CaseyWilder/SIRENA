import calendar

from odoo import api, fields, models
from odoo.addons.l10n_us_hr_payroll.utils.vertex import FED_WH_ID, SOC_SEC_EE_ID, SOC_SEC_ER_ID, MED_EE_ID, MED_ER_ID

TAX_LIST = (FED_WH_ID, SOC_SEC_EE_ID, SOC_SEC_ER_ID, MED_EE_ID, MED_ER_ID)


class TaxLiabilitySemiweekly(models.Model):
    _name = 'semiweekly.tax.report'
    _description = 'Tax Liability for Semiweekly Schedule Depositors Report'

    name = fields.Char('Name', compute='_compute_name', store=True)
    quarter = fields.Selection([('1', 'First'), ('2', 'Second'), ('3', 'Third'), ('4', 'Fourth')], string='Quarter')
    year = fields.Char('Year')

    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id', readonly=True, store=True)
    vat = fields.Char(related='company_id.vat')

    line_ids = fields.One2many('semiweekly.tax.report.line', 'report_id', string='Lines')
    month_1 = fields.Monetary('Tax Liability Month 1')
    month_2 = fields.Monetary('Tax Liability Month 2')
    month_3 = fields.Monetary('Tax Liability Month 3')
    total_tax_liability = fields.Monetary('Total Tax Liability', compute='_compute_total_tax_liability', store=True)

    # Month 1-3
    REPORT_FIELD = ['month_1', 'month_2', 'month_3']

    @api.depends('quarter', 'year')
    def _compute_name(self):
        for record in self:
            record.name = "{} Quarter, {}".format(dict(record._fields['quarter'].selection).get(record.quarter),
                                                  record.year)

    @api.depends('month_1', 'month_2', 'month_3')
    def _compute_total_tax_liability(self):
        for record in self:
            record.total_tax_liability = record.month_1 + record.month_2 + record.month_3

    def _get_tax_info(self, company_id):
        query = """
            SELECT SUM(tax_amt) AS tax_amt,
                DATE_PART('month', pay_date) AS pay_month,
                pay_date
            FROM payslip_tax
            WHERE tax_id IN {}
                AND DATE_PART('year', pay_date) = {}
                AND DATE_PART('quarter', pay_date) = {}
                AND state IN ('done')
                AND company_id = {}
            GROUP BY pay_month, pay_date
            ORDER BY pay_date;
        """.format(TAX_LIST, self.year, int(self.quarter), company_id)

        self.env.cr.execute(query)
        return self.env.cr.dictfetchall()

    def update_report_info(self):
        """
        This main function is to get 941 data from Payslip.
        :return:
        """
        for record in self:
            company_id = record.company_id.id
            # Get Tax Data
            tax_data = record._get_tax_info(company_id)
            line_data = {}
            month_1 = month_2 = month_3 = 0

            for tax in tax_data:
                tax_amt = tax.get('tax_amt', 0)
                pay_date = tax.get('pay_date')
                pay_month = int(tax.get('pay_month', 1))
                offset = 0

                # Tax Liability per month
                if pay_month % 3 == 1:
                    month_1 += tax_amt
                elif pay_month % 3 == 2:
                    month_2 += tax_amt
                    offset = 2
                else:
                    month_3 += tax_amt
                    offset = 4

                line_sequence = pay_month + offset + 1

                if pay_month not in line_data:
                    line_data[pay_month] = {
                        'sequence': pay_month + offset,
                        'data': []
                    }

                line_data[pay_month]['data'].extend([{
                    'amount': tax_amt,
                    'pay_date': pay_date,
                    'sequence': line_sequence
                }])

            line_ids = [(5, 0, 0)]
            for pay_month in line_data:
                line_ids.extend([(0, 0, {
                    'name': calendar.month_name[pay_month],
                    'display_type': 'line_section',
                    'sequence': line_data[pay_month]['sequence']
                })])
                line_ids.extend([(0, 0, x) for x in line_data[pay_month]['data']])

            record.write({
                'line_ids': line_ids,
                'month_1': month_1,
                'month_2': month_2,
                'month_3': month_3,
            })

    def button_print_report_xls(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': '/semiweekly_tax_export/{}'.format(self.id),
            'target': 'current',
        }

    def button_print_report(self):
        self.ensure_one()
        return self.env.ref('l10n_us_hr_payroll_reports.action_report_semiweekly_tax_report').report_action(self)


class TaxLiabilitySemiweeklyLine(models.Model):
    _name = 'semiweekly.tax.report.line'
    _description = 'Tax Liability for Semiweekly Report Line'
    _order = 'sequence, id'

    name = fields.Char('Month')
    report_id = fields.Many2one('semiweekly.tax.report', 'Report', ondelete='cascade')
    quarter = fields.Selection(related='report_id.quarter')
    pay_date = fields.Date('Pay Date')
    currency_id = fields.Many2one('res.currency', related='report_id.currency_id')
    amount = fields.Monetary('Amount')
    display_type = fields.Selection([
        ('line_section', "Section"),
        ('line_note', "Note")], default=False, help="Technical field for UX purpose.")
    sequence = fields.Integer('Sequence')
