odoo.define('l10n_us_hr_payroll_dashboard.payroll_calendar', function (require) {
    'use strict';

    let AbstractField = require('web.AbstractField');
    let core = require('web.core');
    let qweb = core.qweb;
    let registry = require('web.field_registry');

    let PayrollCalendar = AbstractField.extend({

        init: function () {
            this._super.apply(this, arguments);
            this.start_date = null;
            this.end_date = null;
            this.pay_date = null;
            this.deadline = null;
            this.month = false;
            this.next = false;
            this.previous = false;
            this.label = false;
            this.activeDates = null;
            this.date = new Date;
            this.todaysDate = new Date;
        },

        init_data: function() {
            if (this.value) {
                let data = JSON.parse(this.value);
                this.start_date = new Date(data.start_date);
                this.end_date = new Date(data.end_date);
                this.pay_date = new Date(data.pay_date);
                this.deadline = new Date(data.deadline);
            }
            this.month = this.$el.find('[data-calendar-area="month"]')[0];
            this.next = this.$el.find('[data-calendar-toggle="next"]')[0];
            this.previous = this.$el.find('[data-calendar-toggle="previous"]')[0];
            this.label = this.$el.find('[data-calendar-label="month"]')[0];
            this.date.setDate(1);
            this._createMonth();
            this._createListeners();
        },

        /**
         * @private
         */
        _render: function () {
            let self = this;
            if (self.$el.find('.current_period_calendar').length === 0) {
                $(qweb.render('CurrentPeriodCalendar', {})).appendTo($(self.$el).empty());
                self.init_data();
            }
        },

        _createMonth: function () {
            for (let t = this.date.getMonth(); this.date.getMonth() === t;) {
                this._createDay(this.date.getDate(), this.date.getDay(), this.date.getFullYear());
                this.date.setDate(this.date.getDate() + 1);
            }
            this.$el.find('[data-toggle="tooltip"]').tooltip();
            this.date.setDate(1);
            this.date.setMonth(this.date.getMonth() - 1);
            this.label.innerHTML = this._monthsAsString(this.date.getMonth()) + " " + this.date.getFullYear()
            // this._dateClicked();
        },

        _createListeners: function () {
            let self = this;
            this.next.addEventListener("click", function () {
                self._clearCalendar();
                let e = self.date.getMonth() + 1;
                self.date.setMonth(e);
                self._createMonth();
            });
            this.previous.addEventListener("click", function () {
                self._clearCalendar();
                let e = self.date.getMonth() - 1;
                self.date.setMonth(e);
                self._createMonth();
            })
        },

        _createDay: function(date, day, year) {
            let div = document.createElement("div");
            div.className = "vcal-date";
            div.setAttribute("data-calendar-date", this.date);
            (date === 1) && (div.style.marginLeft = 14.28 * day + "%");

            if (this.date.getTime() < this.todaysDate.getTime()) {
                div.classList.add("disabled");
            } else {
                div.classList.add("active");
                div.setAttribute("data-calendar-status", "active");
                this.date.toString() === this.todaysDate.toString() && div.classList.add("today");
            }

            this._update_period_and_tooltip(div);

            let span = document.createElement("span");
            span.innerHTML = date;

            div.appendChild(span);
            this.month.appendChild(div);
        },

        _monthsAsString: function (t) {
            return ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"][t]
        },

        _clearCalendar: function () {
            this.month.innerHTML = ""
        },

        _removeActiveClass: function () {
            for (let t = 0; t < this.activeDates.length; t++) this.activeDates[t].classList.remove("vcal-date--selected")
        },

        _update_period_and_tooltip: function (div) {
            let d = new Date(this.date.getTime());
            d.setHours(0, 0, 0, 0);
            let datetime = d.getTime();
            let start_datetime = this.start_date.getTime();
            let end_datetime = this.end_date.getTime();
            let tooltip = '';

            if (datetime >= start_datetime && datetime <= end_datetime) {
                div.classList.add("period");
                if (datetime === start_datetime) {
                    div.classList.add("start");
                    tooltip += '<div>Start Date</div>';
                }
                if (datetime === end_datetime) {
                    div.classList.add("end");
                    tooltip += '<div>End Date</div>';
                }
            }
            if (datetime === this.deadline.getTime()) {
                div.classList.add("deadline");
                tooltip += '<div>Payroll Submission Deadline</div>';
            }
            if (datetime === this.pay_date.getTime()) {
                div.classList.add("pay");
                tooltip += '<div>Pay Date</div>';
            }
            if (tooltip) {
                div.setAttribute("data-toggle", "tooltip");
                div.setAttribute("title", tooltip);
                div.setAttribute("data-html", "true")
            }
        }
    });

    registry.add("payroll_calendar", PayrollCalendar);
});
