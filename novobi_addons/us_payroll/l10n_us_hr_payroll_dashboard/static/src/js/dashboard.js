odoo.define("l10n_us_hr_payroll_dashboard.payroll_dashboard", function (require) {
    // var JournalDashboardGraph = require("web.JournalDashboardGraph");
    let AbstractField = require('web.AbstractField');
    let core = require('web.core');
    let qweb = core.qweb;
    let registry = require('web.field_registry');

    let CustomDashboard = require('l10n_custom_dashboard.custom_dashboard');

    let PayrollDashboard = CustomDashboard.extend({
        className: "",
        events:{
            'click #period_selection': '_onClickSelection',
            'click #period_group_by': '_onClickGroupBy',
        },

        init: function () {
            this._super.apply(this, arguments);
            this.graph_type = this.attrs.graph_type;
            this.data = JSON.parse(this.value);
            this.startPeriod = null;
            this.endPeriod = null;
            this.group_by = null;
            this.renderSelection = true;
        },

        /**
         * Function to call rpc to retrieve data from model.
         * @param data
         * @param default_param
         * @private
         */
        _retrieveModelData: function(data, default_param) {
            let self = this;
            this._rpc({
                method: data.function_retrieve,
                model: this.model,
                args: default_param.concat(data.extra_param)
            }).then(function (result) {
                self._getData(data.data_type, result);
                self._renderChart();
                self._renderInfo();
            });
        },

        _getData: function(type, data) {
            if (data.constructor === Object) {
                this.graph = {
                    type: type,
                    label: data.label,
                    data: data.data,
                    setting: data.setting,
                };
                this.info = data.info_data;
            }
        },

        //--------------------------------------------------------------------------
        // Event
        //--------------------------------------------------------------------------
        _onClickSelection: function(e) {
            let selection = $(e.target)[0];
            let filter = this.$el.find('span#period_selection_name')[0];
            let period_name = selection.textContent.trim();

            // Update text for time filter
            filter.textContent = period_name;

            // Update start_date, end_date
            let start = selection.getAttribute('start');
            let end = selection.getAttribute('end');
            this.startPeriod = start === 'false' ? false : start;
            this.endPeriod = end === 'false' ? false : end;

            // Update group_by
            let name = this.data.name;
            let group_by = null;
            if (name === 'cost' || name === 'hours') {
                let selection = this.data.selection;
                for (let i in selection) {
                    if (selection[i]['name'] === period_name) {
                        group_by = selection[i].group_by;
                        this.group_by = group_by.length ? group_by[0].value : false;
                        break;
                    }
                }
            }
            this.renderSelection = false;
            this._renderInDOM();
            if (name === 'cost' || name === 'hours') {
                this._renderGroupBy(this.$el.find('.group_by_container'), group_by);
            }
        },

        _onClickGroupBy: function(e) {
            let selection = $(e.target)[0];
            let group_by = this.$el.find('span#period_group_by_name')[0];
            // Update text for group_by
            group_by.textContent = selection.textContent.trim();
            this.group_by = selection.getAttribute('value');
            this.renderSelection = false;
            this._renderInDOM();
        },

        //--------------------------------------------------------------------------
        // Private
        //--------------------------------------------------------------------------

        /**
         * @private: render chart
         */
        _renderInfo: function () {
            let self = this.$el.find('.summarized-view');
            self.empty();
            $(qweb.render('SummarizeView', {
                'info': this.info
            })).appendTo(self);
        },

        /**
         * Render selection on top of chart
         * @param {dict} data
         * @private
         */
        _renderSelection: function(data) {
            if (this.$el.find('.payroll_chart').length === 0) {
                $(qweb.render('TimeFilter', {
                    'type': data.name,
                    'data': data,
                    'group_by': []
                })).appendTo($(this.$el).empty());
            }
            this._renderGroupBy(this.$el.find('.group_by_container'), []);
        },

        _renderGroupBy: function (parent, data) {
            parent.empty();
            $(qweb.render('PeriodGroupBy', {
                'group_by': data
            })).appendTo(parent);
        },

        /**
         * Render the widget. This function assumes that it is attached to the DOM.
         *
         * @private
         */
        _renderInDOM: function () {
            if (this.value) {
                let data = JSON.parse(this.value);
                this.selection = data.selection;

                this.renderSelection && this._renderSelection(data);

                let range = this._getRangePeriod();
                let default_param = [range.start_date, range.end_date, range.group_by];

                if (data.function_retrieve === '') {
                    this._getData(data.data_type, data);
                    this._renderChart();
                } else {
                    this._retrieveModelData(data, default_param);
                }
            }
        },


        //--------------------------------------------------------------------------
        // General
        //--------------------------------------------------------------------------
        /**
         * Get information about the range time and type of period chosen in the
         * selection field.
         *
         * @private
         */
        _getRangePeriod: function () {
            /*
             * Get range of period (start date, end date) after handling event 'click' on time filter selection.
             * If startPeriod and endPeriod have not been set yet, return default of selection (Last Scheduled Period).
             */
            let start = this.startPeriod;
            let end = this.endPeriod;
            if (start && end) {
                return {
                    'start_date': start,
                    'end_date': end,
                    'group_by': this.group_by
                }
            } else {
                for (let i in this.selection) {
                    let item = this.selection[i];
                    if (item.default) {
                        return {
                            'start_date': item.start,
                            'end_date': item.end,
                            'group_by': false
                        }
                    }
                }
            }
            return {};
        },

    });

    registry.add("payroll_dashboard", PayrollDashboard);
});
