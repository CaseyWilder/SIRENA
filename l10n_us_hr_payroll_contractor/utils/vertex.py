from odoo.addons.l10n_us_hr_payroll.utils.vertex import Vertex


def get_payroll_result_list_but_contractors(self, obj):
    """
      Filter out contractors before sending info to vertex to get tax.
       :param obj: payslip_ids
    """
    payslips_without_contractors = obj.filtered(lambda payslip: payslip.employee_type != 'contractor')
    for payslip in payslips_without_contractors:
        xml_request = self._generate_emp(payslip)
        vertex_result = self.vertex_calculate(payslip, xml_request)
        self._create_payslip_tax(vertex_result, payslip)
        self._create_payslip_compout(vertex_result, payslip)


# Monkey patch to override get_payroll_result_list
Vertex.get_payroll_result_list = get_payroll_result_list_but_contractors
