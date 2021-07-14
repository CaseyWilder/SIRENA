from odoo import fields, models, api, _
from odoo.exceptions import ValidationError, UserError

GL_ACCOUNT_FIELDS_MAP = {
    'payroll.compensation': [
        ('account_comp_receivable_id', 'account_receivable_id'),
    ],
    'payroll.tax': [
        ('account_tax_er_payable_id', 'er_account_payable_id'),
        ('account_tax_er_expense_id', 'er_expense_account_id'),
        ('account_tax_ee_payable_id', 'ee_account_payable_id'),     # is_er_tax = False
    ]
}


class GLAccountMixin(models.AbstractModel):
    _name = 'gl.account.mixin'
    _description = 'GL Account Settings Mixin'

    gl_account_setting = fields.Selection(
        [('general', 'General Account'), ('department', 'Per Department'), ('employee', 'Per Employee')],
        string='Account Settings', default='general', required=True)
    gl_account_ids = fields.One2many('gl.account.line', 'compensation_id', string='GL Account')

    @api.onchange('gl_account_setting')
    def _onchange_gl_account_setting(self):
        # Remove all gl_account lines if users change account settings.
        self.gl_account_ids = [(5,)]

    @api.constrains('gl_account_ids')
    def _check_gl_account_unique_employee(self):
        """
        Each employee/department must have no more than 1 account.
        """
        for record in self.filtered(lambda r: r.gl_account_setting != 'general'):
            field = 'employee_id' if record.gl_account_setting == 'employee' else 'department_id'
            ids, duplicates = list(), set()

            for line in record.gl_account_ids:
                if line[field].id in ids:
                    duplicates.add(line[field].name)
                else:
                    ids.append(line[field].id)
            if duplicates:
                names = '- ' + '\n- '.join(name for name in duplicates)
                raise ValidationError(_("""These {} have been added more than one:
                {}\nPlease remove all the duplicates and try again.
                """.format(record.gl_account_setting + 's', names)))

    def get_journal_entry_account(self, employee_id, is_er_tax=None):
        """
        Get configuration accounts from payroll.compensation, payroll.tax to post journal entry
        :param employee_id:
        :param is_er_tax: is this a company tax?
        :return: list of account_id
        """
        self.ensure_one()
        setting = self.gl_account_setting

        fields = GL_ACCOUNT_FIELDS_MAP.get(self._name, []).copy()
        if self._name == 'payroll.tax':
            if is_er_tax:
                del fields[-1]
            else:
                fields = [fields[-1]]

        if setting == 'employee':
            line_id = self.gl_account_ids.filtered(lambda r: r.employee_id == employee_id)
        elif setting == 'department':
            line_id = self.gl_account_ids.filtered(lambda r: r.department_id == employee_id.department_id)
        else:
            line_id = False

        list_account = []
        for field_name in fields:
            list_account.append(line_id and line_id[field_name[0]] or self[field_name[1]])

        return list_account


class GLAccountLine(models.Model):
    _name = 'gl.account.line'
    _description = 'GL Account line for Payroll Compensation/Tax'

    type = fields.Selection([('comp', 'Compensation'), ('tax', 'Tax')], string='Apply for')

    # For Compensation
    compensation_id = fields.Many2one('payroll.compensation', string='Compensation')
    account_comp_receivable_id = fields.Many2one('account.account', string='Salary Expense/Account Receivable', company_dependent=True)

    # For Tax
    tax_id = fields.Many2one('payroll.tax', string='Tax')
    is_er_tax = fields.Boolean(related='tax_id.is_er_tax')
    account_tax_er_payable_id = fields.Many2one('account.account', string='Company Account Payable', company_dependent=True)
    account_tax_er_expense_id = fields.Many2one('account.account', string='Company Expense Account', company_dependent=True)
    account_tax_ee_payable_id = fields.Many2one('account.account', string='Employee Account Payable', company_dependent=True)

    employee_id = fields.Many2one('hr.employee', string='Employee')
    department_id = fields.Many2one('hr.department', string='Department')

    @api.onchange('employee_id')
    def _onchange_employee_id(self):
        """ Each employee must be only 1 line (cannot appear more than 1 time) """
        field = 'compensation_id' if self.type == 'comp' else 'tax_id'
        return {
            'domain': {
                'employee_id': [('id', 'not in', self[field].gl_account_ids.mapped('employee_id').ids)]
            }
        }

    @api.onchange('department_id')
    def _onchange_department_id(self):
        """ Each department must be only 1 line (cannot appear more than 1 time) """
        field = 'compensation_id' if self.type == 'comp' else 'tax_id'
        return {
            'domain': {
                'department_id': [('id', 'not in', self[field].gl_account_ids.mapped('department_id').ids)]
            }
        }
