from odoo import api, fields, models, _

FEDEX_LABEL_STOCK_TYPES = [
    ('PAPER_4X6',                           'Paper 4" x 6"'),
    ('PAPER_4X6.75',                        'Paper 4" x 6.75"'),
    ('PAPER_4X8',                           'Paper 4" x 8"'),
    ('PAPER_4X9',                           'Paper 4" x 9"'),
    ('PAPER_7X4.75',                        'Paper 7" x 4.75"'),
    ('PAPER_8.5X11_BOTTOM_HALF_LABEL',      'Paper 8.5" x 11" Bottom Half Label'),
    ('PAPER_8.5X11_TOP_HALF_LABEL',         'Paper 8.5" x 11" Top Half Label'),
    ('STOCK_4X6',                           'Stock 4" x 6"'),
    ('STOCK_4X6.75',                        'Stock 4" x 6.75"'),
    ('STOCK_4X6.75_LEADING_DOC_TAB',        'Stock 4" x 6.75" with Leading Doc Tab'),
    ('STOCK_4X6.75_TRAILING_DOC_TAB',       'Stock 4" x 6.75" with Trailing Doc Tab'),
    ('STOCK_4X8',                           'Stock 4" x 8"'),
    ('STOCK_4X9',                           'Stock 4" x 9"'),
    ('STOCK_4X9_LEADING_DOC_TAB',           'Stock 4" x 9" with Leading Doc Tab'),
    ('STOCK_4X9_TRAILING_DOC_TAB',          'Stock 4" x 9" with Trailing Doc Tab')
]

UPS_LABEL_STOCK_TYPES = [
    ('4X6', '4" x 6"'),
    ('4X8', '4" x 8"')
]

QUANTITY_COLUMNS = [
    ('done',    'Done'),
    ('demand',  'Demand'),
    ('reserve', 'Reserve')
]


class ShippingAccount(models.Model):
    _inherit = 'shipping.account'

    fedex_label_stock_type = fields.Selection(FEDEX_LABEL_STOCK_TYPES, string="Label Stock Type", default='STOCK_4X6.75_LEADING_DOC_TAB')
    ups_label_stock_type = fields.Selection(UPS_LABEL_STOCK_TYPES, string="Label Stock Type", default='4X8')
    stock_quantity_column = fields.Selection(QUANTITY_COLUMNS, string="Take Products' Quantity From", default='demand')
