from odoo import api, fields, models, _


class Employee(models.Model):
    _inherit = 'hr.employee'

    is_statutory = fields.Boolean('Statutory employee', default=False, groups="hr.group_hr_user",
                                  help="Please refer to the instruction of W2 form, box 13")
    is_third_party_sick_pay = fields.Boolean('Third-party sick pay', default=False, groups="hr.group_hr_user",
                                             help="Please refer to the instruction of W2 form, box 13")
