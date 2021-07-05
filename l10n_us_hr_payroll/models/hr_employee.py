import re
import copy

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
from odoo.tools.float_utils import float_compare, float_round

from .address_mixin import EE_PARTNER_SYNC_FIELDS
from .geocode_mixin import WORK_ADDRESS_LIST, GEO_VALUE_DICT, GEO_WORK_VALUE_DICT
from .payslip_mixin import EE_PAYSLIP_SYNC_FIELDS
from ..utils.utils import sync_record, split_confidential_tracked_fields, _standardize_vals, PAYROLL_CONFIDENTIAL_FIELDS


class EmployeeEthnicity(models.Model):
    _name = 'hr.employee.ethnicity'
    _description = 'Employee Ethnicity'
    _order = 'name'

    name = fields.Char('Ethnicity')

    _sql_constraints = [
        ('name_uniq', 'unique (name)', "Tag name already exists !"),
    ]


class Employee(models.Model):
    _name = 'hr.employee'
    _inherit = ['hr.employee', 'payslip.mixin']

    # Private Information
    ethnicity_id = fields.Many2one('hr.employee.ethnicity', string='Ethnicity')
    veteran_status = fields.Selection([
        ('protected', 'A Protected Veteran'),
        ('not_veteran', 'Not A Veteran'),
        ('not_protected', 'Not A Protected Veteran'),
        ('not_identify', 'Not to identify veteran status')
    ], string='Veteran Status')

    # Recruitment
    hire_date = fields.Date('Hire Date', tracking=True, copy=False)
    old_employee_id = fields.Many2one('hr.employee', 'Link to Old Profile', tracking=True, copy=False)

    # Re-Recruitment
    rehire_date = fields.Date('Rehire Date', tracking=True, copy=False)
    new_employee_id = fields.Many2one('hr.employee', 'Link to New Profile', tracking=True, copy=False)

    # Override
    address_home_id = fields.Many2one('res.partner', ondelete='restrict')
    payslip_ids = fields.One2many('payroll.payslip', 'employee_id', string='Payslips')

    # Split Paychecks
    payment_account_ids = fields.One2many('account.payment.direct', 'employee_id', string='Payment Accounts', copy=True)
    split_paychecks_type = fields.Selection([('percentage', 'By Percentage (%)'), ('amount', 'By Amount ($)')],
                                            string='Split Paychecks', default='percentage', required=1)

    employee_compensation_ids = fields.One2many('employee.compensation', 'employee_id', string='Compensations')
    employee_deduction_ids = fields.One2many('employee.deduction', 'employee_id', string='Deductions')

    @api.model
    def default_get(self, fields_list):
        res = super(Employee, self).default_get(fields_list)
        company_id = self.env.company or False
        if 'address_id' in fields_list:
            res['address_id'] = company_id and company_id.partner_id and company_id.partner_id.id or False
        if 'pay_frequency_id' in fields_list:
            res[
                'pay_frequency_id'] = company_id and company_id.pay_frequency_id and company_id.pay_frequency_id.id or False
        if 'time_tracking_id' in fields_list:
            res[
                'time_tracking_id'] = company_id and company_id.time_tracking_id and company_id.time_tracking_id.id or False
        return res

    ####################################################################################################################
    # CONSTRAINTS
    ####################################################################################################################
    @api.constrains('ssnid')
    def _check_ssnid(self):
        for record in self:
            regex = r"^(?!000|666)[0-8][0-9]{2}-(?!00)[0-9]{2}-(?!0000)[0-9]{4}$"
            if not re.match(regex, record.ssnid):
                raise ValidationError(_('SSN is not in the correct format'))

    @api.constrains('payment_method', 'split_paychecks_type', 'payment_account_ids')
    def _check_payment_account_ids(self):
        """
        :raise ValidationError: * IF payment method is deposit AND all payment accounts are removed
                                * IF split type = percentage AND total percentage != 100
        """
        for record in self:
            if record.payment_method == 'deposit':
                if not record.payment_account_ids:
                    raise ValidationError(_('You have not set any payment account yet!'))
                if record.split_paychecks_type == 'percentage':
                    percentage = sum(record.payment_account_ids.mapped('amount_percentage'))
                    if float_compare(percentage, 100, precision_digits=2) != 0:
                        raise ValidationError(_('Please make sure percentage amounts add up to 100%.'))

    ####################################################################################################################
    # ONCHANGE, COMPUTE/INVERSE
    ####################################################################################################################
    @api.onchange('state_id')
    def _onchange_state_id(self):
        if self.state_id:
            self.update({
                'country_id': self.state_id.country_id,
                'filing_status_id': False,
                'alternate_calculation_id': False
            })

    @api.onchange('work_state_id')
    def _onchange_work_state_id(self):
        if self.work_state_id:
            self.update({
                'work_country_id': self.work_state_id.country_id,
                'work_filing_status_id': False,
                'work_alternate_calculation_id': False,
            })

    @api.onchange('payment_method')
    def _onchange_payment_method(self):
        """
        Remove all payment accounts if changing payment method.
        """
        self.payment_account_ids = [(5,)]

    @api.onchange('split_paychecks_type')
    def _onchange_split_paychecks_type(self):
        """
        If change type of split_paychecks_type => reset amount to 0.
        """
        for record in self.payment_account_ids:
            record.amount_percentage = 0
            record.amount_fixed = 0

    @api.onchange('address_id')
    def _onchange_work_address_id(self):
        address_id = self.address_id
        if address_id:
            self.update({
                'work_street': address_id.street,
                'work_street2': address_id.street2,
                'work_city': address_id.city,
                'work_county': address_id.county,
                'work_state_id': address_id.state_id,
                'work_zip': address_id.zip,
                'work_country_id': address_id.country_id
            })

    def _compute_allocation_count(self):
        """
        Override to change from number_of_days to number_of_hours_display.
        Add domain '|', ('date_to', '=', False), ('date_to', '>=', fields.Date.today())
        """
        data = self.env['hr.leave.allocation'].read_group([
            ('employee_id', 'in', self.ids),
            ('holiday_status_id.active', '=', True),
            ('state', '=', 'validate'),
            '|', ('date_to', '=', False), ('date_to', '>=', fields.Date.today()),
        ], ['number_of_hours_display:sum', 'employee_id'], ['employee_id'])
        rg_results = dict((d['employee_id'][0], d['number_of_hours_display']) for d in data)

        for employee in self:
            employee.allocation_count = rg_results.get(employee.id, 0.0)
            employee.allocation_display = "%g" % employee.allocation_count

    ####################################################################################################################
    # ACTION
    ####################################################################################################################
    def action_choose_geocode(self):
        """
        Open popup form to choose geocode.
        :return: action
        """
        self.ensure_one()
        return {
            'name': _('Select Mailing County'),
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'hr.employee',
            'view_id': self.env.ref('l10n_us_hr_payroll.view_employee_geocode_popup_form').id,
            'res_id': self.id,
            'target': 'new',
            'context': {'employee_id': self.id, 'geocode_updated': True}
        }

    def action_choose_work_geocode(self):
        action = self.action_choose_geocode()
        action['name'] = _('Select Work County')
        action['context']['work_employee_id'] = self.id
        return action

    def set_geo_code(self):
        # Just a trick to save and close the popup
        return True

    def button_generate_holiday_leave(self):
        """
        This button for:
        - Re-generating approved holiday leave requests
        - Cancel and remove invalid (upcoming) holiday leave requests
        """
        self.ensure_one()
        work_state = self.work_state_id
        calendar = self.env['hr.public.holidays'].sudo().search([
            ('state_id', '=', work_state.id),
            ('company_id', '=', self.company_id.id)
        ], limit=1)
        if not calendar:
            raise UserError(_('Please generate public holiday of "{}" before generate holiday leaves for this employee'.format(work_state.name)))

        hr_leave_env = self.env['hr.leave'].with_context(
            tracking_disable=True,
            mail_activity_automation_skip=True,
            leave_fast_create=True,
            leave_skip_state_check=True,
        ).sudo()

        # Remove old time off requests for public holidays of this employee
        removed_leaves = hr_leave_env.search([
            ('employee_id', '=', self.id),
            ('mode_company_id', 'in', [False, self.company_id.id]),
            ('holiday_status_id.public_holiday_id', '!=', False),
            ('date_from', '>=', fields.Datetime.now())
        ])
        if removed_leaves:
            removed_leaves.action_refuse()
            removed_leaves.action_draft()
            removed_leaves.unlink()

        # Find leaves of company to get values for new time off of this employee
        company_leaves = hr_leave_env.search([
            ('holiday_type', '=', 'company'),
            ('holiday_status_id.public_holiday_id', '=', calendar.id),
            ('date_from', '>=', fields.Datetime.now())
        ])
        if not company_leaves:
            raise UserError(_('Cannot find any time off request of the company. Go to Public Holidays > Generate Time Off Request.'))

        # Create new time off requests and approve all.
        values = [holiday._prepare_holiday_values(self) for holiday in company_leaves]
        new_leaves = hr_leave_env.create(values)
        new_leaves.filtered(lambda r: r.validation_type == 'both').action_validate()

        # Disable the outdated leave flag
        self.outdated_holiday_leaves = False

    def button_register_departure(self):
        """
        Open form popup to terminate this employee, using Odoo's "Register Departure"
        :return: action
        """
        self.ensure_one()
        ctx = self._context.copy()
        ctx.update({'not_archived': True})

        return {
            'type': 'ir.actions.act_window',
            'name': _('Register Departure'),
            'res_model': 'hr.departure.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': ctx,
            'views': [[False, 'form']]
        }

    def button_rehire(self):
        """
        Create a new profile for this employee.
        Update Re-Recruitment info for old profile, and Recruitment info for new profile.
        :return:
        """
        self.ensure_one()

        # Create new profile for this employee
        values = {
            'name': self.name + ' (1)',
            'old_employee_id': self.id
        }
        new_employee_id = self.copy(default=values)

        # Update Re-Recruitment info for old profile
        self.write({
            'hire_date': fields.Date.today(),
            'rehire_date': fields.Date.today(),
            'new_employee_id': new_employee_id.id
        })

        # Open new profile in edit mode.
        return {
            'name': 'New Profile for {}'.format(self.name),
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'hr.employee',
            'view_id': self.env.ref('l10n_us_hr_payroll.hr_employee_view_form').id,
            'target': 'current',
            'res_id': new_employee_id.id,
            'context': {
                'form_view_initial_mode': 'edit'
            }
        }

    def button_see_payslip_ids(self):
        self.ensure_one()
        return {
            'name': 'Payslips',
            'view_mode': 'tree,form',
            'res_model': 'payroll.payslip',
            'domain': [('employee_id', '=', self.id), ('state', '=', 'done')],
            'type': 'ir.actions.act_window',
            'target': 'current',
        }

    ####################################################################################################################
    # CRUD
    ####################################################################################################################
    @api.model
    def create(self, values):
        if 'employee_code' not in values:
            values['employee_code'] = self.env['ir.sequence'].next_by_code('hr.employee') or ''

        result = super(Employee, self).create(values)

        # Note: change the order of calling '_sync_related_res_partner' and '_sync_geocode'
        # will create a duplicate res_partner
        result._sync_related_res_partner(values, create=True)
        result._sync_geocode(values)

        return result

    def write(self, values):
        result = super(Employee, self).write(values)
        self._sync_geocode(values)
        if self._context.get('from_partner', False) != '1':
            self.with_context(from_employee='1')._sync_related_res_partner(values)
        return result

    def _init_column(self, column_name):
        if column_name == 'vertex_id':
            self._init_column_vertex_id()

        else:
            super(Employee, self)._init_column(column_name)

    def _init_column_vertex_id(self):
        self._cr.execute("UPDATE hr_employee SET vertex_id = LPAD(id::text, 8, '0') WHERE vertex_id IS NULL")

    @api.model
    def _init_column_employee_code(self):
        """
        This should be call by <function/> in xml instead of _init_column() because the sequence has not been created yet.
        """
        self._cr.execute('SELECT id FROM hr_employee WHERE employee_code IS NULL ORDER BY create_date, name')
        employee_ids = self.env.cr.fetchall()

        sequence = self.env.ref('l10n_us_hr_payroll.seq_hr_employee')
        for emp in employee_ids:
            value = sequence.next_by_id()
            self._cr.execute("UPDATE hr_employee SET employee_code = '{}' WHERE id = {}".format(value, emp[0]))

    @api.model
    def _create_new_res_partner(self, values):
        """
        Create a new res_partner and add its id to field 'address_home_id'.
        :param values
        """
        self.ensure_one()
        values.update({
            'name': self.name,
            'employee_id': self.id,
            'supplier_rank': 1,
        })
        values = _standardize_vals(self.env, 'res.partner', values)
        new_partner = self.env['res.partner'].create(values)
        self.address_home_id = new_partner.id

    ####################################################################################################################
    # HELPER METHODS
    ####################################################################################################################
    def _get_work_state(self):
        """ Overridden function:
            :return working state of employee
        """
        self.ensure_one()
        return self.work_state_id or False

    def _get_remaining_leaves(self):
        """ Overridden function:
        Helper to compute the remaining leaves for the current employees
            :returns dict where the key is the employee id, and the value is the remain leaves
        """
        self._cr.execute("""
            SELECT
                sum(h.number_of_hours_display) AS hours,
                h.employee_id
            FROM
                (
                    SELECT holiday_status_id, number_of_hours_display,
                        state, employee_id
                    FROM hr_leave_allocation
                    UNION
                    SELECT holiday_status_id, (number_of_hours_display * -1) as number_of_hours_display,
                        state, employee_id
                    FROM hr_leave
                ) h
                join hr_leave_type s ON (s.id=h.holiday_status_id)
            WHERE
                h.state='validate' AND
                (s.allocation_type='fixed' OR s.allocation_type='fixed_allocation') AND
                h.employee_id in %s
            GROUP BY h.employee_id""", (tuple(self.ids),))
        return dict((row['employee_id'], row['hours']) for row in self._cr.dictfetchall())

    def _sync_related_res_partner(self, values, create=False):
        """
        Synchronize the res_partner when creating/writing employees.
        :param values
        :param create:  * if True:  Create new res_partner has employee_id = current employee.id
                        * else:     Check address_home_id
                            * if True:  Update res_partner
                            * else:     Create new res_partner
        """
        for record in self:
            if create:
                values = sync_record(dict(), values, EE_PARTNER_SYNC_FIELDS)
                record._create_new_res_partner(values)
            else:
                res_partner = record.address_home_id
                if res_partner:
                    if any(ele in values for ele in EE_PARTNER_SYNC_FIELDS):
                        sync_values = sync_record(res_partner, values, EE_PARTNER_SYNC_FIELDS)
                        if sync_values:
                            res_partner.write(sync_values)
                else:
                    for field in EE_PARTNER_SYNC_FIELDS:
                        try:
                            values.update({field: record[field].id})
                        except AttributeError:
                            values.update({field: record[field]})
                    record._create_new_res_partner(values)

    def _sync_geocode(self, values):
        """
        Update Geocode for Mailing and Working Address`
        :param values:
        :return:
        """
        if any(ele in values for ele in GEO_VALUE_DICT.values()):
            self._update_geocode(values, 'employee_id')

        if any(ele in values for ele in GEO_WORK_VALUE_DICT.values()):
            self._update_geocode(values, 'work_employee_id', WORK_ADDRESS_LIST, GEO_WORK_VALUE_DICT)

    def _track_subtype(self, init_values):
        """
        Set subtype used in def message_track() based on init_values.
        If any value in init_values belongs to CONFIDENTIAL_FIELDS => return Confidential subtype.
        :param init_values: dict(key: field name, value: new value)
        :return: subtype
        """
        if any(field in PAYROLL_CONFIDENTIAL_FIELDS for field in init_values):
            return self.env.ref('l10n_us_hr_payroll.mt_employee_confidential_message')
        else:
            return super(Employee, self)._track_subtype(init_values)

    def message_track(self, tracked_fields, initial_values):
        """
        Split all tracked fields into 2 dict: confidential (in Payroll) and normal (in Employee).
        :param tracked_fields: all fields having param track_visibility
        :param initial_values: all initial values of employees changed.
        """
        confidential_fields, normal_fields = split_confidential_tracked_fields(tracked_fields)
        tracking = dict()
        if confidential_fields:
            tracking.update(super(Employee, self).message_track(confidential_fields, initial_values))
        if normal_fields:
            tracking.update(super(Employee, self).message_track(normal_fields, initial_values))
        return tracking

    def copy_payroll_data(self, sync_fields=EE_PAYSLIP_SYNC_FIELDS, incl_comp=False, incl_deduc=False):
        """
        Copy payroll-related data from employee
        :param sync_fields: list of fields need to be sync.
        :param incl_comp:   set True if want to include compensations
        :param incl_deduc:  set True if want to include deductions
        :return: list of dictionary
        """
        def get_copy_payroll_data(employee):
            values = {'employee_id': employee.id}

            for field in fields:
                try:
                    values[field] = employee[field].id
                except AttributeError:
                    values[field] = employee[field]

            if incl_comp:
                compensation_ids = [line.copy_data(default={'is_regular': True})[0] for line
                                    in employee.employee_compensation_ids] if employee.employee_compensation_ids else []
                values['compensation_ids'] = [(0, 0, line) for line in compensation_ids]

            if incl_deduc:
                deduction_ids = [line.copy_data(default={
                    'is_regular': True,
                    'employee_deduction_id': line.id
                })[0] for line in employee.employee_deduction_ids] if employee.employee_deduction_ids else []
                values['deduction_ids'] = [(0, 0, line) for line in deduction_ids]

            return values

        payroll_data = []
        fields = copy.deepcopy(sync_fields)

        # Copy data from no employee -> Should return False values instead of nothing.
        if not self:
            return [get_copy_payroll_data(self)]

        for record in self:
            payroll_data.append(get_copy_payroll_data(record))

        return payroll_data
