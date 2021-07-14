from odoo import models, fields, api


class ExportHistoricalDataWizard(models.TransientModel):
    _name = 'export.historical.data.wizard'
    _description = 'Add Compensations, Deductions to Payslip and export data'

    def _get_payslip_ids_domain(self):
        return [('pay_period_id', '=', self._context.get('active_id', False))]

    name = fields.Char('Name', default='Export')
    payroll_compensation_ids = fields.Many2many('payroll.compensation', string='Compensations')
    payroll_deduction_ids = fields.Many2many('payroll.deduction', string='Deductions')
    period_id = fields.Many2one('pay.period', string='Period')
    payslip_ids = fields.Many2many('payroll.payslip', string='Payslip', domain=_get_payslip_ids_domain)

    def button_add_compensation(self):
        self.ensure_one()
        for payslip in self.payslip_ids:
            new_compensation_ids = self.payroll_compensation_ids - payslip.wizard_compensation_ids
            if new_compensation_ids:
                payslip.wizard_compensation_ids = [(4, comp_id.id) for comp_id in new_compensation_ids]

    def button_add_deduction(self):
        self.ensure_one()
        for payslip in self.payslip_ids:
            new_deduction_ids = self.payroll_deduction_ids - payslip.wizard_deduction_ids
            if new_deduction_ids:
                payslip.wizard_deduction_ids = [(4, ded_id.id) for ded_id in new_deduction_ids]

    def button_export_payslip_compensation(self):
        """
        Export only payslips and their compensations in payslip_ids table of this wizard.
        :return: act_url
        """
        self.ensure_one()
        str_id = '-'.join(map(str, self.payslip_ids.ids))
        return {
            'type': 'ir.actions.act_url',
            'url': '/period_export_payslip_compensation/{}'.format(str_id),
            'target': 'current',
        }

    def button_export_payslip_deduction(self):
        """
        Export only payslips and their deductions in payslip_ids table of this wizard.
        :return: act_url
        """
        self.ensure_one()
        str_id = '-'.join(map(str, self.payslip_ids.ids))
        return {
            'type': 'ir.actions.act_url',
            'url': '/period_export_payslip_deduction/{}'.format(str_id),
            'target': 'current',
        }

    def button_export_payslip_tax(self):
        """
        Export all
        :return: act_url
        """
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': '/period_export_payslip_tax/{}'.format(self.period_id.id),
            'target': 'current',
        }
