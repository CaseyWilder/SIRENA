from odoo import models, fields, api, _


class PayrollDashboard(models.Model):
    _inherit = 'payroll.dashboard'

    def get_period_id_in_frequency(self, frequency_id):
        period_id = super().get_period_id_in_frequency(frequency_id)
        period_id_without_contractors = period_id.filtered(lambda pp: not pp.contain_contractor)
        return period_id_without_contractors

    def _get_domain_pending_leaves(self):
        domain = super()._get_domain_pending_leaves()
        exclude_contractors_domain = ('employee_id.employee_type', '!=', 'contractor')
        domain.append(exclude_contractors_domain)
        return domain

    def _get_domain_pending_paid(self):
        domain = super()._get_domain_pending_paid()
        exclude_contractors_domain = ('employee_type', '!=', 'contractor')
        domain.append(exclude_contractors_domain)
        return domain

    def _get_domain_term_payroll(self):
        domain = super()._get_domain_term_payroll()
        exclude_contractors_domain = ('contain_contractor', '!=', True)
        domain.append(exclude_contractors_domain)
        return domain

    def _get_domain_total_employees(self):
        domain = super()._get_domain_total_employees()
        exclude_contractors_domain = ('employee_type', '!=', 'contractor')
        domain.append(exclude_contractors_domain)
        return domain

    def _get_domain_absent_employees(self):
        domain = super()._get_domain_absent_employees()
        exclude_contractors_domain = ('employee_id.employee_type', '!=', 'contractor')
        domain.append(exclude_contractors_domain)
        return domain

    def _get_domain_fulltime_employees(self):
        domain = super()._get_domain_fulltime_employees()
        exclude_contractors_domain = ('employee_type', '!=', 'contractor')
        domain.append(exclude_contractors_domain)
        return domain

    def _get_domain_parttime_employees(self):
        domain = super()._get_domain_parttime_employees()
        exclude_contractors_domain = ('employee_type', '!=', 'contractor')
        domain.append(exclude_contractors_domain)
        return domain

    def build_birthday_query(self):
        query = super().build_birthday_query()
        exclude_contractors_domain = " AND employee_type != \'contractor\'"
        # Remove ; at last position of original query and add where condition
        birthday_without_contractors_query = query.strip()[:-1] + exclude_contractors_domain
        return birthday_without_contractors_query

    def _sql_retrieve(self, type, start, end, group_by):
        sql, param = super()._sql_retrieve(type, start, end, group_by)
        if sql and (type == 'tbd' or type == 'gross'):
            exclude_contractors_domain = " AND ps.employee_type != \'contractor\' "
            group_by_position = sql.find('GROUP')
            sql = sql[:group_by_position] + exclude_contractors_domain + sql[group_by_position:]
        if sql and type == 'cost':
            sql = sql.replace('total_gross_pay', 'total_gross_pay_without_contractors')
        return sql, param
