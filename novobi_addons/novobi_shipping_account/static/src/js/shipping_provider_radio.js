odoo.define('multichannel_fulfillment.shipping_provider_selection', function (require) {
    "use strict";

    var FieldRadio = require('web.relational_fields').FieldRadio;
    var registry = require('web.field_registry');
    var core = require('web.core');
    var qweb = core.qweb;

    var FieldRadioShippingProvider = FieldRadio.extend({
        _renderReadonly: function () {
            if (this.value){
                var $logo = $('<img width="120"/>');
                $logo.attr("src", "/multichannel_fulfillment/static/src/img/" + this.value + ".png");
                if (this.value == 'ups'){
                    $logo.attr('width', '250');
                }
                this.$el.empty().append($logo);
            }

        },
        _renderEdit: function () {
            var self = this;
            var currentValue;
            if (this.field.type === 'many2one') {
                currentValue = this.value && this.value.data.id;
            } else {
                currentValue = this.value;
            }
            this.$el.empty();
            _.each(this.values, function (value, index) {
                var $html = $(qweb.render('FieldRadio.button', {
                    checked: value[0] === currentValue,
                    id: self.unique_id + '_' + value[0],
                    index: index,
                    value: value,
                }));
                var $logo = $('<img width="120"/>');
                $logo.attr("src", "/multichannel_fulfillment/static/src/img/" + value[0] + ".png");
                $html.find('label').html($logo);
                if (value[0] == 'ups'){
                    $logo.attr('width', '250');
                }
                self.$el.append($html);
            });
        },
    })
    registry.add('shipping_provider_radio', FieldRadioShippingProvider)
})