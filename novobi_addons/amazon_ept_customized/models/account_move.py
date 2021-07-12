import time
import logging
from odoo import fields, models, api, _
from odoo.addons.iap.tools import iap_tools
from odoo.addons.amazon_ept.endpoint import DEFAULT_ENDPOINT

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):

    _inherit = 'account.move'

    @api.model
    def send_amazon_refund_via_email(self, args={}):
        """
        SRN-71
        Override: update fields to v.14:
            sent -> is_move_sent
            type -> move_type
            ('state', 'in', ['open', 'paid']) -> ('state', '=', 'posted')
        """

        instance_obj = self.env['amazon.instance.ept']
        seller_obj = self.env['amazon.seller.ept']
        invoice_obj = self.env['account.move']
        seller_id = args.get('seller_id', False)
        if seller_id:
            seller = seller_obj.search([('id', '=', seller_id)])
            if not seller:
                return True
            email_template = self.env.ref('account.email_template_edi_invoice', False)
            instances = instance_obj.search([('seller_id', '=', seller.id)])
            for instance in instances:
                if instance.refund_tmpl_id:
                    email_template = instance.refund_tmpl_id
                invoices = invoice_obj.search([('amazon_instance_id', '=', instance.id), ('is_move_sent', '=', False),
                                               ('state', '=', 'posted'), ('move_type', '=', 'out_refund')])
                for invoice in invoices:
                    email_template.send_mail(invoice.id)
                    invoice.write({'is_move_sent': True})
        return True

    def upload_odoo_invoice_to_amazon(self, args={}):
        """
        SRN-71
        Override: update fields to v.14:
            type -> move_type
            invoice_payment_state in ('open','paid') -> state = 'posted'
        """
        seller_obj = self.env['amazon.seller.ept']
        feed_submit_obj = self.env['feed.submission.history']
        seller_id = args.get('seller_id', False)
        after_req = 0.0
        if not seller_id:
            _logger.info(_("Seller Id not found in Cron Argument, Please Check Cron Configurations."))
            return True
        seller = seller_obj.browse(seller_id)
        if seller.invoice_upload_policy != 'custom':
            _logger.info(_("Please Verify Invoice Upload Policy Configuration, from Seller Configuration Panel."))
            return True
        instances = seller.instance_ids
        if seller.amz_upload_refund_invoice:
            refund_inv = "and move_type in ('out_invoice', 'out_refund')"
        else:
            refund_inv = "and move_type = 'out_invoice'"
        for instance in instances:
            query = "select id from account_move where amazon_instance_id=%s and state = 'posted' and is_move_sent = False %s" % (
                instance.id, refund_inv)
            self._cr.execute(query)
            invoice_ids = self._cr.fetchall()
            for invoice_id in invoice_ids:
                invoice = self.browse(invoice_id)
                kwargs = invoice._prepare_amz_invoice_upload_kwargs(instance)
                before_req = time.time()
                diff = int(after_req - before_req)
                if 3 > diff > 0:
                    time.sleep(3 - diff)
                response = iap_tools.iap_jsonrpc(DEFAULT_ENDPOINT + '/iap_request', params=kwargs, timeout=1000)
                after_req = time.time()
                if response.get('reason'):
                    _logger.info(_(response.get('reason')))
                    # raise UserError(_(response.get('reason')))
                results = response.get('result')
                if results.get('FeedSubmissionInfo', {}).get('FeedSubmissionId', {}).get('value', False):
                    last_feed_submission_id = results.get('FeedSubmissionInfo', {}).get('FeedSubmissionId', {}).get(
                        'value', False)
                    values = {'feed_result_id': last_feed_submission_id,
                              'feed_submit_date': time.strftime("%Y-%m-%d %H:%M:%S"),
                              'instance_id': instance.id, 'user_id': self._uid,
                              'feed_type': 'upload_invoice',
                              'seller_id': seller_id,
                              'invoice_id': invoice_id}
                    feed = feed_submit_obj.create(values)
                    invoice.write({'is_move_sent': True, 'feed_id': feed.id})
                    self._cr.commit()
        return True