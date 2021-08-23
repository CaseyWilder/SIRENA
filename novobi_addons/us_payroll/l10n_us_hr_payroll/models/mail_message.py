from odoo import models, fields, api


class MailMessage(models.Model):
    _inherit = 'mail.message'

    user_id = fields.Many2one('res.users', 'Belong to User')
    is_confidential = fields.Boolean('Is confidential?', compute='_compute_is_confidential', store=True)

    @api.depends('subtype_id')
    def _compute_is_confidential(self):
        # Use try - except in case creating new db and installing Payroll, _compute_is_confidential is triggered
        # but this subtype has not been installed yet => raise error.
        try:
            subtype_id = self.env.ref('l10n_us_hr_payroll.mt_employee_confidential_message').id
            for record in self:
                record.is_confidential = True if record.subtype_id.id == subtype_id else False
        except ValueError:
            pass

    @api.model
    def create(self, values):
        """
        Check if this message is confidential and belongs to hr_employee => add user_id value for it
        to use in domain filter.
        :param values
        :return: mail_message
        """
        subtype = values.get('subtype_id', False)
        employee = values.get('res_id', False)
        model = values.get('model', False)

        if model == 'hr.employee' and employee:
            employee_id = self.env['hr.employee'].browse(employee)
            user_id = employee_id and employee_id.user_id
            try:
                subtype_id = self.env.ref('l10n_us_hr_payroll.mt_employee_confidential_message')
                if subtype_id and subtype_id.id == subtype and user_id:
                    values['user_id'] = user_id.id
            except ValueError:
                pass

        return super(MailMessage, self).create(values)
