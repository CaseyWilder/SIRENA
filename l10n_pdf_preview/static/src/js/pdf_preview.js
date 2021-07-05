odoo.define('l10n_pdf_tab.ReportPreview', function (require) {
    'use strict';

    let ActionManager = require('web.ActionManager');
    let core = require('web.core');
    let _t = core._t;
    let session = require('web.session');

    ActionManager.include({
        /**
         * @Overwrite
         * Open report in new tab instead of downloading file
         */
        _downloadReport: function (url) {
            var type = 'qweb-' + url.split('/')[2];
            var params = {
                data: JSON.stringify([url, type]),
                context: JSON.stringify(session.user_context),
                token: new Date().getTime()
            };
            var url = session.url('/report/preview', params);
            if (!window.open(url)) {
                var message = _t('A popup window with your report was blocked. You ' +
                    'may need to change your browser settings to allow ' +
                    'popup windows for this page.');
                this.do_warn(_t('Warning'), message, true);
            }
            return $.Deferred().resolve();
        },
    })
});
