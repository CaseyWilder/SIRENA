from odoo import models, api, fields, _


class PayrollSummaryReport(models.AbstractModel):
    _inherit = "payroll.summary.report"

    def build_where_clause(self, extra_where):
        where_clause = super().build_where_clause(extra_where)
        exclude_contractors_statement = " AND SLIP.employee_type != \'contractor\'"
        return where_clause + exclude_contractors_statement
