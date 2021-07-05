import xml.etree.ElementTree as ET
import requests
import html
from datetime import date

from odoo import _
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_is_zero, float_compare, float_round

from .vertex_templates import VERTEX_HEADER, VERTEX_DATE_FORMAT, REQUEST_TEMPLATE, QUERY_PREFIX, CAL_PREFIX, \
    FED_WH_ID, FUTA_ID, SOC_SEC_EE_ID, MED_EE_ID, SOC_SEC_ER_ID, MED_ER_ID, STATE_WH_ID, COUNTY_WH_ID, CITY_WH_ID, SUI_ID, \
    GEOCODE_TMPL, TAXNAME_TMPL, FILING_STATUS_TMPL, ALTERNATE_TMPL, EMPSTRUCT_TMPL, DEDUCT_TMPL, CMP_TMPL, WRK_TMPL, \
    JUR_TMPL, JUR_EXEMPT_TMPL, JUR_ALT_TMPL, OVERRIDE_TMPL, AGGCMP_TMPL, AGGTAX_TMPL, FORM_DATA_ELEMENT_TMPL


class Vertex:

    def vertex_calculate(self, obj, xml_request):
        config = obj.env['ir.config_parameter'].sudo()
        url = config.get_param('vertex-url')
        request = REQUEST_TEMPLATE.format(html.escape(xml_request))
        VERTEX_HEADER.update({
            'x-api-key': config.get_param('x-api-key')
        })

        # Handle Vertex exception
        try:
            response = requests.request("POST", url, headers=VERTEX_HEADER, data=request)
        except:
            raise UserError(_('Network error! Please contact the administrator.'))
        if response.status_code != 200:
            raise UserError(_('Odoo cannot reach Payroll Service! Please try again later.'))
        elif not response.text or response.text == 'null\n':
            raise UserError(_('System error! Please contact the administrator.'))

        content = html.unescape(response.text).replace('<?xml version="1.0" encoding="UTF-8"?>', '')
        return ET.fromstring(content).find(".//return")

    ########################
    # HELPER FUNCTION
    ########################
    def _find_element(self, element, name, is_cal=True):
        prefix = CAL_PREFIX if is_cal else QUERY_PREFIX
        return element.find(prefix + name).text.strip()

    def _split_geocode(self, geocode):
        """
        For QUERY request, Vertex doesn't use GeoCode, but 3 separate components.
        :param geocode
        :return: GeoState: 1 or 2 first digits
                 GeoCnty: 3 middle digits
                 GeoCity: 4 last digits
        """
        geocity = geocode[-4:]
        geocnty = geocode[-7:-4]
        geostate = geocode[:-7]
        return geostate, geocnty, geocity

    def _get_specific_geocode(self, geocode):
        """
        Sometimes we need the State or County geocode. Geocode city is the Geocode itself.
        """
        geostate = geocode.replace(geocode[-7:], str('0' * 7))
        geocnty = geocode.replace(geocode[-4:], str('0' * 4))
        return geostate, geocnty

    ########################
    # GENERATE XML REQUEST
    ########################
    def _generate_geocode(self, partner, value_dict):
        return GEOCODE_TMPL.format(
            partner[value_dict['state_id']].code,
            partner[value_dict['county']] or '',
            partner[value_dict['city']] or '',
            partner[value_dict['zip']]
        )

    def _generate_taxname_request(self, taxid, pay_date, geocode):
        geostate, geocnty, geocity = self._split_geocode(geocode)
        return TAXNAME_TMPL.format(pay_date, taxid, geostate, geocnty, geocity)

    def _generate_filing_status_request(self, date, geostate):
        return FILING_STATUS_TMPL.format(date, geostate)

    def _generate_alternate_calculation_request(self, date, vertex_id):
        return ALTERNATE_TMPL.format(date, vertex_id)

    def _generate_empstruct(self, employee, payslip):
        # TODO: Primary work address might be different for multi states
        period_id = payslip.pay_period_id
        ptd_aggregation = 1 if payslip.pay_type == 'bonus' else 0
        supplemental_method = 2 if payslip.pay_type == 'bonus' else 1

        return EMPSTRUCT_TMPL.format(
            employee.vertex_id,
            period_id.pay_date.strftime(VERTEX_DATE_FORMAT),
            period_id.number_periods,
            period_id.current_period,
            supplemental_method,
            payslip.geocode,
            payslip.work_geocode,
            ptd_aggregation
        )

    def _generate_deductarray(self, payslip):
        deductarray = ""

        if payslip.is_history:
            return ""

        # We need to group Deduction amount by Category
        deduction_dict = {}
        for ded in payslip.deduction_ids.filtered(lambda x: x.vertex_id):
            ded_id = ded.vertex_id
            amount = deduction_dict.get(ded_id, 0)
            amount += ded.amount
            deduction_dict[ded_id] = amount

        for ded, amt in deduction_dict.items():
            deductarray += DEDUCT_TMPL.format(ded, amt, 0)

        return """<DEDUCTARRAY>{}</DEDUCTARRAY>""".format(deductarray)

    def _generate_empinfo(self, employee, payslip):
        empstruct = self._generate_empstruct(employee, payslip)
        deductarray = self._generate_deductarray(payslip) if payslip.deduction_ids else ""

        return """<EMPINFO>{}{}</EMPINFO>""".format(empstruct, deductarray)

    def _generate_wrk(self, payslip):
        # TODO: work in multi states in 1 period
        cmparray = ""
        # Only send pre-tax compensation to Vertex (PAYROLL-461)
        for com in payslip.compensation_ids.filtered(lambda r: not r.is_posttax):
            com_type = 's' if payslip.pay_type == 'bonus' else 'r'
            # TODO: For history, how should we define the amount here
            com_amt = 200 if com.is_history else com.amount

            cmparray += CMP_TMPL.format(com.vertex_id, com_type, com_amt)

        return WRK_TMPL.format(payslip.work_geocode, payslip.total_hours, cmparray)

    def _generate_jurarray(self, payslip):
        content = self._generate_jurarray_content(payslip)
        return """<JURARRAY>{}</JURARRAY>""".format(content) if content.replace(' ', '') else ""

    def _generate_jurarray_content(self, payslip):
        """
        Generate the body content of JURARRAY, so we can override in other modules.
        :param payslip: payslip of 1 employee
        :return: body content
        """
        work_geocode = payslip.work_geocode
        geocode = payslip.geocode
        work_state_code, work_county_code = self._get_specific_geocode(work_geocode)
        state_code, county_code = self._get_specific_geocode(geocode)

        # Filing Status + Allowance
        fed_jur = self._generate_jur(pri_exem=payslip.fed_allow, filing_status_id=payslip.fed_filing_status_id)

        # State Allowance
        state_jur = self._generate_jur(work_state_code,
                                       payslip.work_state_pri_allow,
                                       payslip.work_state_sec_allow,
                                       filing_status_id=payslip.work_filing_status_id)
        if not payslip.is_same_state:
            state_jur += self._generate_jur(state_code,
                                            payslip.state_pri_allow,
                                            payslip.state_sec_allow,
                                            filing_status_id=payslip.filing_status_id)

        # County Allowance
        county_jur = self._generate_jur(work_county_code, payslip.work_county_allow)
        if not payslip.is_same_county:
            county_jur += self._generate_jur(county_code, payslip.county_allow)

        # City Allowance
        city_jur = self._generate_jur(work_geocode, payslip.work_city_allow)
        if not payslip.is_same_city:
            city_jur += self._generate_jur(geocode, payslip.city_allow)

        # Tax Exemption
        federal_tax_jur = self._generate_jur_exempt(FED_WH_ID) if payslip.exempt_federal_tax else ''
        social_security_jur = self._generate_jur_exempt(SOC_SEC_EE_ID) + self._generate_jur_exempt(SOC_SEC_ER_ID) \
            if payslip.exempt_social_security else ''
        medicare_jur = self._generate_jur_exempt(MED_EE_ID) + self._generate_jur_exempt(MED_ER_ID) if payslip.exempt_medicare else ''

        # Alternate Calculation
        work_alt = payslip.work_alternate_calculation_id
        live_alt = payslip.alternate_calculation_id
        alternate_cal = self._generate_jur_alt_calculation(work_alt.tax_id, work_state_code, work_alt.vertex_id) if work_alt else ''
        if not payslip.is_same_state and live_alt:
            alternate_cal += self._generate_jur_alt_calculation(live_alt.tax_id, state_code, live_alt.vertex_id)

        return fed_jur + state_jur + county_jur + city_jur + federal_tax_jur + social_security_jur + medicare_jur + alternate_cal

    def _generate_jur(self, geocode=0, pri_exem=0, sec_exem=0, tax_id=-1, filing_status_id=None):
        jur_filing = "<FILING_STAT>{}</FILING_STAT>".format(filing_status_id.vertex_id) if filing_status_id else ''
        return JUR_TMPL.format(tax_id, geocode, jur_filing, pri_exem, sec_exem)

    def _generate_jur_exempt(self, tax_id, geocode='000000000', tax_exempt=1):
        return JUR_EXEMPT_TMPL.format(tax_id, geocode, tax_exempt)

    def _generate_jur_alt_calculation(self, tax_id, geocode, alt_calc):
        return JUR_ALT_TMPL.format(tax_id, geocode, alt_calc)

    def _generate_overridearray(self, payslip):
        content = self._generate_overridearray_content(payslip)
        return """<OVERRIDEARRAY>{}</OVERRIDEARRAY>""".format(content) if content.replace(' ', '') else ""

    def _generate_overridearray_content(self, payslip):
        company_id = payslip.employee_id.company_id
        pay_date = payslip.pay_date
        # Additional Withholding
        work_geocode = payslip.work_geocode
        geocode = payslip.geocode
        work_state_code, work_county_code = self._get_specific_geocode(work_geocode)
        state_code, county_code = self._get_specific_geocode(geocode)

        # Federal
        fed_ov = self._generate_override(FED_WH_ID, add_wh=payslip.fed_add_wh) if payslip.fed_add_wh else ""

        # State
        state_ov = self._generate_override(STATE_WH_ID, geo=work_state_code, add_wh=payslip.work_state_add_wh)\
            if payslip.work_state_add_wh else ""
        state_ov += self._generate_override(STATE_WH_ID, geo=state_code, add_wh=payslip.state_add_wh)\
            if not payslip.is_same_state and payslip.state_add_wh else ""

        # County
        county_ov = self._generate_override(COUNTY_WH_ID, geo=work_county_code, add_wh=payslip.work_county_add_wh)\
            if payslip.work_county_add_wh else ""
        county_ov += self._generate_override(COUNTY_WH_ID, geo=county_code, add_wh=payslip.county_add_wh)\
            if not payslip.is_same_county and payslip.county_add_wh else ""

        # City
        city_ov = self._generate_override(CITY_WH_ID, geo=work_geocode, add_wh=payslip.work_city_add_wh)\
            if payslip.work_city_add_wh else ""
        city_ov += self._generate_override(CITY_WH_ID, geo=geocode, add_wh=payslip.city_add_wh)\
            if not payslip.is_same_city and payslip.city_add_wh else ""

        # FUTA
        futa_tax_rate = company_id.futa_tax_rate/100
        futa_ov = self._generate_override(FUTA_ID, tax_rate=futa_tax_rate) if company_id.override_futa_rate else ""

        # SUI Tax
        work_state_id = payslip.work_state_id.id
        sui_tax = payslip.env['sui.tax'].search([
            ('company_id', '=', company_id.id),
            ('state_id', '=', work_state_id),
            ('start_date', '<=', pay_date),
            ('end_date', '>=', pay_date),
        ], limit=1)
        sui_tax_rate = sui_tax and sui_tax.tax_rate/100
        sui_ov = self._generate_override(SUI_ID, geo=work_state_code, tax_rate=sui_tax_rate) if sui_tax_rate else ""

        return fed_ov + state_ov + county_ov + city_ov + futa_ov + sui_ov

    def _generate_override(self, tax_id, geo='000000000', add_wh=None, tax_rate=None):
        additional_tax = '<ADDITIONAL_TAX>{}</ADDITIONAL_TAX>'.format(add_wh) if add_wh else ''
        ov_rate = '<OV_RATE>{}</OV_RATE>'.format(tax_rate) if tax_rate else ''

        return OVERRIDE_TMPL.format(tax_id, geo, ov_rate + additional_tax)

    def _generate_aggcmparray(self, last_payslip, ptd_aggregation):
        aggcmparray = ""
        for compout in last_payslip.compout_ids:
            # Year-to-Date
            aggcmparray += AGGCMP_TMPL.format(compout.tax_id, compout.geocode, compout.school_dist, compout.comp_id,
                                              compout.comp_type, compout.ytd_amount, 'Y')

            # Period-to-Date
            if ptd_aggregation:
                aggcmparray += AGGCMP_TMPL.format(compout.tax_id, compout.geocode, compout.school_dist, compout.comp_id,
                                                  compout.comp_type, compout.amt, 'P')

        return """<AGGCMPARRAY>{}</AGGCMPARRAY>""".format(aggcmparray) if aggcmparray else ""

    def _generate_taxamtarray(self, last_payslip, ptd_aggregation):
        taxamtarray = ""
        for tax in last_payslip.tax_ids:
            # Year-to-Date
            taxamtarray += AGGTAX_TMPL.format(tax.tax_id, tax.geocode, tax.school_dist, tax.ytd_amount, 'Y', tax.agg_adj_gross)

            # Period-to-Date
            if ptd_aggregation:
                taxamtarray += AGGTAX_TMPL.format(tax.tax_id, tax.geocode, tax.school_dist, tax.tax_amt, 'P', tax.actual_adjusted_gross)

        return """<TAXAMTARRAY>{}</TAXAMTARRAY>""".format(taxamtarray) if taxamtarray else ""

    def _generate_form_data(self, payslip):
        multiple_jobs = self._generate_form_data_element('US_FED.W4.MULTIPLE_JOBS', 1 if payslip.multiple_jobs else 0)
        claim_dependents = self._generate_form_data_element('US_FED.W4.DEPENDENTS', payslip.claim_dependents and 0)
        other_income = self._generate_form_data_element('US_FED.W4.OTHER_INCOME', payslip.other_income)
        other_deduction = self._generate_form_data_element('US_FED.W4.DEDUCTIONS', payslip.other_deduction)

        return """<FORM_DATA>{} {} {} {}</FORM_DATA>""".format(multiple_jobs, claim_dependents, other_income, other_deduction)

    def _generate_form_data_element(self, form_name, form_value, geocode='000000000', tax_type=2):
        return FORM_DATA_ELEMENT_TMPL.format(geocode, tax_type, form_name, form_value)

    def _generate_emp(self, payslip):
        employee = payslip.employee_id
        empinfo = self._generate_empinfo(employee, payslip)
        wrk = self._generate_wrk(payslip)
        jurarray = self._generate_jurarray(payslip)

        aggcmparray = ''
        taxamtarray = ''
        overridearray = self._generate_overridearray(payslip)

        # Search for previous payslip
        period_id = payslip.pay_period_id
        pay_date = payslip.pay_date
        year = pay_date.year

        payslip_ids = employee.payslip_ids.filtered(lambda x:
                                                    date(year, 1, 1) <= x.pay_date <= date(year, 12, 31)
                                                    and x.state == 'done'
                                                    and x.company_id == payslip.company_id
                                                    and x.id != payslip.id)
        if payslip_ids:
            last_payslip = payslip_ids.sorted(key=lambda x: x.pay_date, reverse=True)[0]
            ptd_aggregation = True if period_id.pay_type == 'bonus' else False
            aggcmparray = self._generate_aggcmparray(last_payslip, ptd_aggregation)
            taxamtarray = self._generate_taxamtarray(last_payslip, ptd_aggregation)

        # New W4 Information
        form_data = self._generate_form_data(payslip)

        # Note: Must be in the same order as the schema:
        # EMPINFO > WRK > JURARRAY > AGGCMPARRAY > TAXAMTARRAY > OVERRIDEARRAY > CANADIAN_ARRAY > FORM_DATA > QUANTUM > ..
        return """<?xml version="1.0" encoding="UTF-8"?>
        <EMP>{}</EMP>""".format(empinfo + wrk + jurarray + aggcmparray + taxamtarray + overridearray + form_data)

    def get_geocode(self, obj, option_field, value_dict):
        """
        Function to get geocode.
        :param obj: the model that needs to get geocode. In this project: hr.employee
        :param option_field: the relational field to link with geocode.option
        :param value_dict: field name to get value and send to Vertex
        :return:
        """
        xml_request = self._generate_geocode(obj, value_dict)
        response = self.vertex_calculate(obj, xml_request)

        response_geocodes = response.findall('.//Geocodes')
        result = []

        # Remove all other geocode of this employee
        GeocodeOption = obj.env['geocode.option'].sudo()
        GeocodeOption.search([(option_field, '=', obj.id)]).unlink()

        if response_geocodes:
            for code in response_geocodes:
                record = GeocodeOption.create({
                    option_field: obj.id,
                    'geocode': code.find('GEO').text.strip(),
                    'city': code.find('CityName').text.strip().capitalize(),
                    'county': code.find('CountyName').text.strip().capitalize(),
                    'state': code.find('StateName').text.strip().capitalize(),
                    'zip_from': code.find('ZipStart').text.strip(),
                    'zip_to': code.find('ZipEnd').text.strip()
                })
                result.append(record)

        return result

    def get_filing_status(self, obj, date):
        # obj is res.country.state, or Federal if False
        geostate = obj.vertex_id if obj else 0
        geocode = obj.geocode if obj else '0'
        is_federal = not geostate
        pay_date = date.strftime(VERTEX_DATE_FORMAT)

        xml_request = self._generate_filing_status_request(pay_date, geostate)
        response = self.vertex_calculate(obj, xml_request)

        FilingStatus = obj.env['filing.status'].sudo()
        update_ids = []

        for element in response.iter(QUERY_PREFIX + 'ELEMENT'):
            if self._find_element(element, 'GEO', is_cal=False) != geocode:
                continue

            filing_id = self._find_element(element, 'FILING_STAT', is_cal=False)
            filing_name = self._find_element(element, 'FILSTAT_DESC', is_cal=False)

            filing_status_id = FilingStatus.search([('vertex_id', '=', filing_id)], limit=1)
            if not filing_status_id:
                filing_status_id = FilingStatus.create({
                    'vertex_id': filing_id,
                    'name': filing_name,
                    'is_federal': is_federal
                })
            elif is_federal:
                filing_status_id.is_federal = True

            update_ids.append(filing_status_id.id)

        return update_ids

    def get_alternate_calculation(self, obj, date):
        # obj is res.country.state
        vertex_id = obj.vertex_id
        geocode = obj.geocode
        pay_date = date.strftime(VERTEX_DATE_FORMAT)

        xml_request = self._generate_alternate_calculation_request(pay_date, vertex_id)
        response = self.vertex_calculate(obj, xml_request)

        AlternateCal = obj.env['alternate.calculation'].sudo()
        update_ids = []

        for element in response.iter(QUERY_PREFIX + 'ELEMENT'):
            if self._find_element(element, 'GEO', is_cal=False) != geocode:
                continue

            vertex_id = self._find_element(element, 'ID', is_cal=False)

            calculation_id = AlternateCal.search([('vertex_id', '=', vertex_id)], limit=1)
            if not calculation_id:
                tax_id = self._find_element(element, 'TAXID', is_cal=False)
                schdist = self._find_element(element, 'SCHDIST', is_cal=False)
                tax_name = self._find_element(element, 'TAXNAME', is_cal=False)
                desc = self._find_element(element, 'ALT_CALC_CD_DESC', is_cal=False)

                calculation_id = AlternateCal.create({'vertex_id': vertex_id,
                                                      'tax_id': tax_id,
                                                      'school_dist': schdist,
                                                      'tax_name': tax_name,
                                                      'name': desc})

            update_ids.append(calculation_id.id)

        return update_ids

    def _get_tax_name(self, obj, taxid, pay_date, geocode, general_tax_name):
        # obj is payroll.payslip

        PayrollTax = obj.env['payroll.tax'].sudo()
        result = False
        tax_obj = PayrollTax.search([('tax_id', '=', taxid),
                                     ('geocode', '=', geocode)], limit=1)

        if tax_obj:
            result = tax_obj
        else:
            xml_request = self._generate_taxname_request(taxid, pay_date, geocode)
            response = self.vertex_calculate(obj, xml_request)

            results = response.findall('.//' + QUERY_PREFIX + 'ELEMENT')
            if len(results) != 0:
                full_tax_name = self._find_element(results[0], 'TAXNAME', is_cal=False)
                school_dist = self._find_element(results[0], 'SCHDIST', is_cal=False)
                is_er_tax = True if general_tax_name[:2] == 'ER' else False

                result = PayrollTax.create({'name': full_tax_name,
                                            'tax_id': taxid,
                                            'geocode': geocode,
                                            'school_dist': school_dist,
                                            'is_er_tax': is_er_tax})

        return result

    def get_payroll_result_list(self, obj):
        """
        Generate the request and create payslip tax, compOut from the response.
        :param obj: payslip_ids
        """
        for payslip in obj:
            xml_request = self._generate_emp(payslip)
            vertex_result = self.vertex_calculate(payslip, xml_request)

            self._create_payslip_tax(vertex_result, payslip)
            self._create_payslip_compout(vertex_result, payslip)

    def _create_payslip_tax(self, vertex_result, payslip):
        """
        Create Payslip tax from values of vertex_result.
        :param payslip: payroll.payslip record
        :param vertex_result
        :return:
        """
        pay_date = payslip.pay_period_id.pay_date.strftime(VERTEX_DATE_FORMAT)
        PayslipTax = payslip.env['payslip.tax'].sudo()
        company = payslip.company_id

        for tax in vertex_result.iter(CAL_PREFIX + 'TaxOut'):
            tax_id = self._find_element(tax, 'TAXID')
            general_tax_name = self._find_element(tax, 'TAXNAME')
            geocode = self._find_element(tax, 'GEO')
            tax_obj = self._get_tax_name(payslip, tax_id, pay_date, geocode, general_tax_name)
            med_add_tax_wages = med_add_tax_amt = 0

            # Additional Medicare Withholding
            if tax_id == MED_EE_ID:
                for form in vertex_result.iter(CAL_PREFIX + 'FORM_RESULT_ELEMENT'):
                    form_name = self._find_element(form, 'FORM_DATA_NAME')
                    form_value = self._find_element(form, 'FORM_DATA_VALUE_USED')
                    if form_name == 'MEDICARE.ADDITIONALTAXWAGES':
                        med_add_tax_wages = form_value
                    elif form_name == 'MEDICARE.ADDITIONALTAXAMT':
                        med_add_tax_amt = form_value

            amount = float_round(float(self._find_element(tax, 'TAX_AMT')), precision_digits=2) if not payslip.is_history else 0
            adjusted_gross = self._find_element(tax, 'ADJ_GROSS') if not payslip.is_history else payslip.gross_pay

            PayslipTax.create({
                'payslip_id': payslip.id,
                'payroll_tax_id': tax_obj.id if tax_obj else False,
                'company_id': company.id if company else False,
                'name': general_tax_name,
                'tax_id': tax_id,
                'geocode': geocode,
                'school_dist': self._find_element(tax, 'SCHDIST'),
                'tax_amt': amount,
                'adjusted_gross': adjusted_gross,
                'subject_gross_amt': self._find_element(tax, 'SUBJ_GRS'),
                'taxable_gross_amt': self._find_element(tax, 'TAXABLE_GROSS'),
                'base_amt_used': self._find_element(tax, 'BASE_AMT_USED'),
                'exempt_amt_used': self._find_element(tax, 'EXEMPT_AMT_USED'),
                'filing_status': self._find_element(tax, 'FILING_STAT'),
                'max_deduction_amt': self._find_element(tax, 'MAX_DED_AMT_USED'),
                'rate_used': self._find_element(tax, 'RATE_USED'),
                'med_add_tax_wages': med_add_tax_wages,
                'med_add_tax_amt': med_add_tax_amt,
            })

    def _create_payslip_compout(self, vertex_result, payslip):
        """
        Create Payslip compOut from values of vertex_result.
        :param payslip: payroll.payslip record
        :param vertex_result:
        :return:
        """
        PayslipCompout = payslip.env['payslip.compout'].sudo()
        company = payslip.company_id

        history_comp = {}
        if payslip.is_history:
            for com in payslip.compensation_ids:
                com_id = com.compensation_id.vertex_id
                amount = history_comp.get(com_id, 0)
                amount += com.amount
                history_comp[com_id] = amount

        for comp_out in vertex_result.iter(CAL_PREFIX + 'CompOut'):
            com_id = self._find_element(comp_out, 'ID_USED')
            result_amt = float(self._find_element(comp_out, 'AmtAllowed'))
            amount = result_amt
            if payslip.is_history:
                # result amt = 0 => 0, otherwise, use our actual amount
                amount = history_comp.get(com_id, 0) if not float_is_zero(result_amt, precision_digits=1) else 0

            PayslipCompout.create({
                'payslip_id': payslip.id,
                'company_id': company.id if company else False,
                'tax_name': self._find_element(comp_out, 'TAXNAME'),
                'tax_id': self._find_element(comp_out, 'TAXID'),
                'geocode': self._find_element(comp_out, 'GEO'),
                'tax_type': self._find_element(comp_out, 'TAX_TYPE'),
                'school_dist': self._find_element(comp_out, 'SCHDIST'),
                'comp_id': com_id,
                'comp_type': self._find_element(comp_out, 'TYPE'),
                'amt': amount,
            })
