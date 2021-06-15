/**
 * Copyright © 2020 Novobi, LLC
 * See LICENSE file for full copyright and licensing details.
 */
odoo.define('novobi_shipping_account.CancelCreateLabelButton', function (require) {
    "use strict";

    const Widget = require('web.Widget');
    const widgetRegistry = require('web.widget_registry');

    const CancelCreateLabelButton = Widget.extend({
        template: 'NovobiShippingAccount.CancelCreateLabelButton',
        className: 'btn btn-secondary',
        events: {
            'click': '_onClickCancel',
        },
        init: function (parent, record) {
            this._super.apply(this, arguments);
            this.parent = parent;
            this.resId = record.res_id;
        },
        _onClickCancel: function() {
            this._resetLabelFields().then(() => this._closeWizard());
        },
        _resetLabelFields: function() {
            return this._rpc({
                model: 'stock.picking',
                method: 'reset_label_fields',
                args: [this.resId],
            });
        },
        _closeWizard: function () {
            this.do_action({type: 'ir.actions.act_window_close'});
        }
    });

    widgetRegistry.add('cancel_create_label_button', CancelCreateLabelButton);

    return CancelCreateLabelButton;
});
