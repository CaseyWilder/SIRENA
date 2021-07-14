# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class PrintPreNumberedChecks(models.TransientModel):
    _inherit = 'print.prenumbered.checks'

    def print_checks(self):
        payslip_ids = self._context.get('payslip_ids', False)
        if payslip_ids:
            payslips = self.env['payroll.payslip'].browse(payslip_ids)
            # Set check number
            next_check_number = int(self[0].next_check_number)
            for payslip in payslips:
                payslip.check_date = fields.Datetime.now()
                payslip.check_number = next_check_number
                next_check_number += 1

            return payslips.do_print_check()
        else:
            return super(PrintPreNumberedChecks, self).print_checks()
