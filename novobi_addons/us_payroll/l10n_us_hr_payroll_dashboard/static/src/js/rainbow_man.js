odoo.define('l10n_us_hr_payroll_dashboard.payroll_rainbow_man', function (require) {
    'use strict';

    var AbstractField = require('web.AbstractField');
    var core = require('web.core');
    var qweb = core.qweb;

    var RainbowMan = require('web.RainbowMan');

    RainbowMan.include({
        /**
         * @override
         */
        init: function(options) {
            if (options.payroll_custom) {
                this.template = 'PayrollRainbowMan';
            }
            return this._super.apply(this, arguments);
        },

        start: function () {
            var custom = this.options.payroll_custom;
            var self = this;
            if (custom !== undefined) {
                // Click anywhere on screen to close rainbow_man.
                if (custom.close_on_click) {
                    core.bus.on('click', this, function (ev) {
                        if (ev.originalEvent && ev.target.className.indexOf('o_reward') === -1) {
                            this.destroy();
                        }
                    });
                }
                // Auto close after delay time.
                if (custom.delay && custom.delayTime) {
                    setTimeout(function () {
                        self.$el.addClass('o_reward_fading');
                        setTimeout(function () {
                            self.destroy();
                        }, 600); // destroy only after fadeout animation is completed
                    }, custom.delayTime);
                }
                this.$('.o_reward_msg_content').append(this.options.message);
            } else {
                return this._super.apply(this, arguments);
            }
        }
    });

    var PayrollRainbowMan = AbstractField.extend({
        className: "w-100",

        init: function () {
            this._super.apply(this, arguments);
            this.options = this.value ? JSON.parse(this.value) : false;
        },

        /**
         * @private
         */
        _render: function () {
            this._super.apply(this, arguments);
            if (this.options) {
                new RainbowMan(this.options).appendTo(this.$el);
                // this.trigger_up('show_effect', options);
            }
        }
    });

    var registry = require('web.field_registry');

    registry.add("payroll_rainbow_man", PayrollRainbowMan);
});
