odoo.define('l10n_us_hr_payroll.Dialog', function (require) {
   "use strict";

   let Dialog = require('web.Dialog');

   Dialog.include({
       /**
        * Intercept action handling to increase z-index of the last modal in order to blur the others.
        * @override
        */
       open: function () {
           this._super.apply(this, arguments);
           this.opened(function () {
               let modals_backdrop = $('.modal-backdrop.show');
               let modals = $('[role=dialog]');
               let length = modals.length;

               if (length > 1) {
                   var z_index = $(modals[length - 2]).css('z-index');
                   $(modals_backdrop[length - 1]).css('z-index', ++z_index);
                   $(modals[length - 1]).css('z-index', ++z_index);
               }
           });
           return this;
       }
   })
});
