from odoo import fields, models, api, _
from odoo.exceptions import UserError


class AddMissingEmpWizard(models.TransientModel):
    _name = 'add.missing.emp.wizard'
    _description = 'Add missing employees to scheduled period'

    def _get_employee_ids_domain(self):
        period_id = self.env.context.get('default_period_id', False)
        if period_id:
            period_id = self.env['pay.period'].browse(period_id)
            return period_id._get_missing_employees_domain()
        else:
            return []

    period_id = fields.Many2one('pay.period', string='Pay Period')
    employee_ids = fields.Many2many('hr.employee', string='Employees', domain=_get_employee_ids_domain)
    
    def button_add_missing_employees(self):
        self.ensure_one()
        if not self.employee_ids:
            raise UserError(_('Please choose at least one employee.'))

        payslip_data = self.employee_ids.copy_payroll_data(incl_comp=True, incl_deduc=True)
        self.period_id.write({
            'payslip_ids': [(0, 0, line) for line in payslip_data]
        })
