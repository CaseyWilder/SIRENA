VERTEX_HEADER = {
    'Content-Type': "text/xml; charset=utf-8",
}
VERTEX_DATE_FORMAT = '%Y%m%d'
REQUEST_TEMPLATE = """<?xml version="1.0" ?>
    <S:Envelope xmlns:S="http://schemas.xmlsoap.org/soap/envelope/">
        <S:Body>
            <ns2:EiOperation xmlns:ns2="http://EiCalc/">
                <Request>{}</Request>
            </ns2:EiOperation>
        </S:Body>
    </S:Envelope>
"""

QUERY_PREFIX = "{urn:vertexinc:qpay:EI:QueryResponse}"
CAL_PREFIX = "{urn:vertexinc:qpay:EI:CalcResponse}"

FED_WH_ID = "400"
FUTA_ID = "402"
SOC_SEC_EE_ID = "403"
MED_EE_ID = "406"
SOC_SEC_ER_ID = "404"
MED_ER_ID = "407"
STATE_WH_ID = "450"
COUNTY_WH_ID = "501"
CITY_WH_ID = "530"
SUI_ID = "459"

BYPASS_METHOD = "16"

WORKER_COMP_EE_ID = "470"
WORKER_COMP_ER_ID = "471"

GEOCODE_TMPL = """
    <EI_GEOCODE_REQUEST>
        <State>{}</State>
        <County>{}</County>
        <City>{}</City>
        <Zip>{}</Zip>
    </EI_GEOCODE_REQUEST>
"""

TAXNAME_TMPL = """
    <QUERY>
        <PAYDATE>{}</PAYDATE>
        <TAXID>{}</TAXID>
        <GEOSTATE>{}</GEOSTATE>
        <GEOCNTY>{}</GEOCNTY>
        <GEOCITY>{}</GEOCITY>
        <GET>
            <TAXNAMES/>
        </GET>
    </QUERY>
"""

FILING_STATUS_TMPL = """
    <QUERY>
        <PAYDATE>{}</PAYDATE>
        <GEOSTATE>{}</GEOSTATE>
        <GET>
            <VAL_FIL_STATS/>
        </GET>
    </QUERY>
"""

ALTERNATE_TMPL = """
    <QUERY>
        <PAYDATE>{}</PAYDATE>
        <GEOSTATE>{}</GEOSTATE>
        <GET>
            <VAL_ALT_CALC_CDS/>
        </GET>
    </QUERY>
"""

EMPSTRUCT_TMPL = """
    <EMPSTRUCT>
        <EMPID>{}</EMPID>
        <PAYDATE>{}</PAYDATE>
        <PAYPERIODS>{}</PAYPERIODS>
        <CURPERIOD>{}</CURPERIOD>
        <SUPL_METH>{}</SUPL_METH>
        <RES_GEO>{}</RES_GEO>
        <PRIMARY_WORK_GEO>{}</PRIMARY_WORK_GEO>
        <PTD_AGG_FLAG>{}</PTD_AGG_FLAG>
    </EMPSTRUCT>
"""

DEDUCT_TMPL = """
    <DEDUCT>
        <ID>{}</ID>
        <Amt>{}</Amt>
        <VALUE_TYPE>{}</VALUE_TYPE>
    </DEDUCT>
"""

CMP_TMPL = """
    <CMP>
        <ID>{}</ID>
        <TYPE>{}</TYPE>
        <Amt>{}</Amt>
    </CMP>
"""

WRK_TMPL = """
    <WRK>
        <WRKINFO>
            <GEO>{}</GEO>
            <NUMHOURS>{}</NUMHOURS>
        </WRKINFO>
        <CMPARRAY>
            {}
        </CMPARRAY>
    </WRK>
"""

JUR_TMPL = """
    <JUR>
        <TAXID>{}</TAXID>
        <GEO>{}</GEO>
        {}
        <PRI_EXEMPT>{}</PRI_EXEMPT>
        <SEC_EXEMPT>{}</SEC_EXEMPT>
    </JUR>
"""

JUR_EXEMPT_TMPL = """
    <JUR>
        <TAXID>{}</TAXID>
        <GEO>{}</GEO>
        <TAX_EXEMPT>{}</TAX_EXEMPT>
    </JUR>
"""

JUR_ALT_TMPL = """
    <JUR>
        <TAXID>{}</TAXID>
        <GEO>{}</GEO>
        <ALTCALC>{}</ALTCALC>
    </JUR>
"""

OVERRIDE_TMPL = """
    <OVERRIDE>
        <TAXID>{}</TAXID>
        <GEO>{}</GEO>
        {}
    </OVERRIDE>
"""

AGGCMP_TMPL = """
    <AGGCMP>
        <TAXID>{}</TAXID>
        <GEO>{}</GEO>
        <SCHDIST>{}</SCHDIST>
        <ID>{}</ID>
        <TYPE>{}</TYPE>
        <Amt>{}</Amt>
        <AGGTYPE>{}</AGGTYPE>
    </AGGCMP>
"""

AGGTAX_TMPL = """
    <AGGTAX>
        <TAXID>{}</TAXID>
        <GEO>{}</GEO>
        <SCHDIST>{}</SCHDIST>
        <TAX_AMT>{}</TAX_AMT>
        <AGG_TYPE>{}</AGG_TYPE>
        <AGG_ADJ_GROSS>{}</AGG_ADJ_GROSS>
    </AGGTAX>
"""

FORM_DATA_ELEMENT_TMPL = """
    <FORM_DATA_ELEMENT>
        <GEO>{}</GEO>
        <TAX_TYPE>{}</TAX_TYPE>
        <FORM_DATA_NAME>{}</FORM_DATA_NAME>
        <FORM_DATA_VALUE>{}</FORM_DATA_VALUE>
    </FORM_DATA_ELEMENT>
"""

# GENERAL REQUEST STRUCTURE
# <EMP>
#     <EMPINFO>
#         <EMPSTRUCT></EMPSTRUCT>
#
#         <DEDUCTARRAY>
#             <DEDUCT></DEDUCT>
#         </DEDUCTARRAY>
#     </EMPINFO>
#
#     <WRK>
#         <WRKINFO></WRKINFO>
#         <CMPARRAY>
#             <CMP></CMP>
#         </CMPARRAY>
#     </WRK>
#
#     <JURARRAY>
#         <JUR></JUR>
#     </JURARRAY>
#
#     <OVERRIDEARRAY>
#         <OVERRIDE></OVERRIDE>
#     </OVERRIDEARRAY>
#
#     <AGGCMPARRAY>
#         <AGGCMP></AGGCMP>
#     </AGGCMPARRAY>
#
#     <TAXAMTARRAY>
#         <AGGTAX></AGGTAX>
#     </TAXAMTARRAY>
# </EMP>
