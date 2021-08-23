odoo.define('multichannel_fulfillment.custom_radio_selected_value', function (require) {
    "use strict";

    var FieldRadio = require('web.relational_fields').FieldRadio;
    var registry = require('web.field_registry');

    var FieldRadioSelectedValue = FieldRadio.extend({
        _renderEdit: function () {
            var invisible_values = this.nodeOptions.invisible_values;
            if (invisible_values != undefined){
                var selected_values = [];
                _.each(this.values, function(e){
                    if (!invisible_values.includes(e[0])){
                        selected_values.push(e)
                    }
                })
                this.values = selected_values
            }
            this._super.apply(this, arguments);
        }
    })

    registry.add('field_radio_selected_value', FieldRadioSelectedValue)

})