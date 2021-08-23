from odoo import api, models


class MailTemplate(models.Model):
    _inherit = 'mail.template'

    def generate_email(self, res_ids, fields=None):
        results = super().generate_email(res_ids=res_ids, fields=fields)
        model = self.model

        if model != 'payroll.payslip':
            return results

        multi_mode = True
        if isinstance(res_ids, int):
            multi_mode = False
            res_ids = [res_ids]

        payslip_env = self.env[model]
        if multi_mode:
            for res_id, values in results.items():
                payslip = payslip_env.browse(res_id)
                for key, value in values.items():
                    if key == 'attachments':
                        attachments = []
                        # Value is a list of tuple (name, binary_data)
                        for attachment in value:
                            name, encoded_string = \
                                payslip._set_report_password(attachment[0], attachment[1])
                            attachments += [(name, encoded_string)]
                        results[res_id]['attachments'] = attachments

        else:
            # results is a dictionary
            payslip = payslip_env.browse(results.get('res_id'))
            for key, value in results.items():
                if key == 'attachments':
                    attachments = []
                    # Value is a list of tuple (name, binary_data)
                    for attachment in value:
                        name, encoded_string = \
                            payslip._set_report_password(attachment[0], attachment[1])
                        attachments += [(name, encoded_string)]
                    results['attachments'] = attachments

        return results
