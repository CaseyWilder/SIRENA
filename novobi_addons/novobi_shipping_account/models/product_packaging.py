# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

from odoo import fields, models
import logging

_logger = logging.getLogger(__name__)


class ProductPackaging(models.Model):
    _inherit = 'product.packaging'

    is_custom = fields.Boolean("Is Custom ?", copy=False)
    is_require_dimensions = fields.Boolean("Require Dimensions", copy=False)
    height = fields.Float('Height', copy=False)
    width = fields.Float('Width', copy=False)
    length = fields.Float('Length', copy=False)

