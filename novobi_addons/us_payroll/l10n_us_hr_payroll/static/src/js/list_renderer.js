odoo.define('l10n_us_hr_payroll.ListRenderer', function (require) {
    "use strict";

    var ListRenderer = require('web.ListRenderer');

    ListRenderer.include({
        init: function (parent, state, params) {
            this._super.apply(this, arguments);
            if (state.context.disable_selector) {
                this.hasSelectors = false;
            }
        },
    });
});
