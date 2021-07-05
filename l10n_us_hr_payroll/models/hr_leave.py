# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, tools


class HrLeave(models.Model):
    _inherit = 'hr.leave'

    number_of_hours_display = fields.Float(store=True)

    @api.depends('number_of_days', 'date_from', 'date_to')
    def _compute_number_of_hours_display(self):
        return super()._compute_number_of_hours_display()


class HolidaysAllocation(models.Model):
    _inherit = "hr.leave.allocation"

    number_of_hours_display = fields.Float(store=True)


class HrLeaveType(models.Model):
    _inherit = 'hr.leave.type'

    payroll_compensation_id = fields.Many2one('payroll.compensation', string='Compensation')

    emp_type_salary_ovt = fields.Boolean('Apply for Salary/Eligible for Overtime', default=True)
    emp_type_salary = fields.Boolean('Apply for Salary/No Overtime', default=True)
    emp_type_hourly = fields.Boolean('Apply for Hourly', default=True)

    leave_ids = fields.One2many('hr.leave', 'holiday_status_id', string='Leave Requests',
                                domain=[('state', '=', 'validate'), ('employee_id', '!=', False)])


class LeaveReport(models.Model):
    _inherit = 'hr.leave.report'

    number_of_hours_display = fields.Float('Number of Hours', readonly=True)

    def init(self):
        """
        Override this function for adding number_of_hours_display
        """
        tools.drop_view_if_exists(self._cr, 'hr_leave_report')

        self._cr.execute("""
            CREATE or REPLACE view hr_leave_report as (
                SELECT row_number() over(ORDER BY leaves.employee_id) as id,
                leaves.employee_id as employee_id, leaves.name as name,
                leaves.number_of_hours_display as number_of_hours_display,
                leaves.number_of_days as number_of_days, leaves.leave_type as leave_type,
                leaves.category_id as category_id, leaves.department_id as department_id,
                leaves.holiday_status_id as holiday_status_id, leaves.state as state,
                leaves.holiday_type as holiday_type, leaves.date_from as date_from,
                leaves.date_to as date_to, leaves.payslip_status as payslip_status
                from (select
                    allocation.employee_id as employee_id,
                    allocation.private_name as name,
                    allocation.number_of_hours_display as number_of_hours_display,
                    allocation.number_of_days as number_of_days,
                    allocation.category_id as category_id,
                    allocation.department_id as department_id,
                    allocation.holiday_status_id as holiday_status_id,
                    allocation.state as state,
                    allocation.holiday_type,
                    null as date_from,
                    null as date_to,
                    FALSE as payslip_status,
                    'allocation' as leave_type
                from hr_leave_allocation as allocation
                union all select
                    request.employee_id as employee_id,
                    request.private_name as name,
                    (request.number_of_hours_display * -1) as number_of_hours_display,
                    (request.number_of_days * -1) as number_of_days,
                    request.category_id as category_id,
                    request.department_id as department_id,
                    request.holiday_status_id as holiday_status_id,
                    request.state as state,
                    request.holiday_type,
                    request.date_from as date_from,
                    request.date_to as date_to,
                    request.payslip_status as payslip_status,
                    'request' as leave_type
                from hr_leave as request) leaves
            );
        """)
