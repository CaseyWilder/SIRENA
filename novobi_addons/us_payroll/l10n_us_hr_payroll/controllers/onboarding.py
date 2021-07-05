from odoo import http
from odoo.http import request


class OnboardingController(http.Controller):

    @http.route('/us_payroll/payroll_dashboard_onboarding', auth='user', type='json')
    def us_payroll_dashboard_onboarding(self):
        """ Returns the `banner` for the US Payroll dashboard onboarding panel.
            It can be empty if the user has closed it or if he doesn't have
            the permission to see it. """
        company = request.env.user.company_id

        if not request.env.user._is_admin() or \
                company.us_payroll_dashboard_onboarding_state == 'closed':
            return {}

        return {
            'html': request.env.ref('l10n_us_hr_payroll.payroll_dashboard_onboarding_panel')._render({
                'company': company,
                'state': company.get_and_update_us_payroll_dashboard_onboarding_state()
            })
        }
