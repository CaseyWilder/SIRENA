odoo.define('multichannel_fulfillment.get_rate_button', function (require) {
    "use strict";

    const DebouncedField = require('web.basic_fields').DebouncedField;
    const registry = require('web.field_registry');
    const formatMonetary = require('web.field_utils').format.monetary;
    const session = require('web.session');

    const GetRateButton = DebouncedField.extend({
        template: 'GetRateButton',
        className: 'get_rate_button',
        supportedFieldTypes: ['float'],
        events: {
            'click button': 'get_rate',
        },

        init: function (parent, name, record, options) {
            this._super.apply(this, arguments);
            const currencyField = this.nodeOptions.currency_field || this.field.currency_field || 'currency_id';
            const currencyID = this.record.data[currencyField] && this.record.data[currencyField].res_id;
            this.currency = session.get_currency(currencyID);
        },

        _getValue: function () {
            return this.value
        },

        resetValue(){
            let children = this.getParent().getChildren();
            let error_message = _.find(children, c => c.name === 'error_message');
            let estimated_date_field = _.find(children, c => c.name === 'estimated_done_date');
            let shipping_cost_without_discounts = _.find(children, c => c.name === 'shipping_cost_without_discounts');
            let defs = [];
            let render = [];
            defs.push(this._setValue('0.00'));
            if (estimated_date_field){
                defs.push(estimated_date_field._setValue(""));
                render.push(estimated_date_field);
            }
            if (shipping_cost_without_discounts){
                defs.push(shipping_cost_without_discounts._setValue("0.00"));
                render.push(shipping_cost_without_discounts);
            }
            if (error_message){
                defs.push(error_message._setValue(""));
                render.push(error_message);
            }
            Promise.all(defs).then(function () {
                _.each(render, function(e){
                    e._render();
                })
            });
        },

        showRate: function (result) {
            let children = this.getParent().getChildren();
            let error_message = _.find(children, c => c.name === 'error_message');
            let estimated_date_field = _.find(children, c => c.name === 'estimated_done_date');
            let shipping_cost_without_discounts = _.find(children, c => c.name === 'shipping_cost_without_discounts');
            let value = '0.00';
            let render = [];
            let defs = [];
            if (result['error_message']) {
                defs.push(error_message._setValue(result['error_message']));
                render.push(error_message);
                if (estimated_date_field.value !== 'ERROR!') {
                    defs.push(estimated_date_field._setValue('ERROR!'));
                    render.push(estimated_date_field);
                }
                defs.push(shipping_cost_without_discounts._setValue('0.00'));
                render.push(shipping_cost_without_discounts);
            }
            else {
                let price = result['price'] ? result['price'].toString() : '0.00';
                let priceWithoutDiscounts = result['price_without_discounts'] ? result['price_without_discounts'].toString() : '0.00';

                value = price;
                defs.push(shipping_cost_without_discounts._setValue(priceWithoutDiscounts));
                render.push(shipping_cost_without_discounts);

                let estimated_date = result['estimated_date'] || ' ';
                let momentDate = moment(estimated_date);
                estimated_date = momentDate.isValid() ? momentDate.format('L') : estimated_date;
                if (estimated_date_field.value !== estimated_date) {
                    defs.push(estimated_date_field._setValue(estimated_date));
                    render.push(estimated_date_field);
                }

                if (error_message){
                    defs.push(error_message._setValue(""));
                    render.push(error_message);
                }

            }
            defs.push(this._setValue(value));
            Promise.all(defs).then(function () {
                _.each(render, function(e){
                    e._render();
                })
            });
            this.$el.find('.loader').hide();
            this.$el.find('.btn-link').show();
        },

        get_rate: function () {
            let handle = this.getParent().getParent().handle;
            let options = {
                stayInEdit: true,
                reload: true,
                savePoint: false
            };
            this.resetValue();
            let controller = this.getParent().getParent();
            controller.saveRecord(handle, options).then(function(){
                let self = this;
                self.$el.find('.loader').show();
                self.$el.find('.btn-link').hide();
                self._rpc({
                    method: 'get_carrier_rate',
                    model: 'stock.picking',
                    args: [[this.record.res_id]]
                }, {shadow: true})
                    .then(self.showRate.bind(self))
                    .catch(function (error) {
                        self.$el.find('.loader').hide();
                        self.$el.find('.btn-link').show();
                    });
            }.bind(this));
        },

        _render: function(){
            this._super.apply(this, arguments);
            if (this.value !== undefined){
                let value = formatMonetary(this.value, null, {currency: this.currency});
                this.$el.find('.estimated_shipping_rate_value').html(value)
            }
        }
    });

    registry.add('get_rate_button', GetRateButton)
});