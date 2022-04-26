# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, exceptions , _
from odoo.exceptions import Warning, UserError
import tempfile
import binascii
from tempfile import TemporaryFile
from ast import literal_eval
import logging
from odoo.tools.float_utils import float_compare, float_is_zero, float_repr, float_round
from odoo.osv import expression

_logger = logging.getLogger(__name__)

try:
	import xlrd
except ImportError:
	_logger.debug('Cannot `import xlrd`.')


class import_lot_wizard(models.TransientModel):

	_name = 'import.lot.wizard'
	_description = "Import Lot/Serial No Single Product"

	select_lot = fields.Selection([('serial','Serial No'),('lot','Lot No')],string="Selection",default='serial')
	lot_file = fields.Binary(string="Select File")
	stock_move_id = fields.Many2one('stock.move')
	
	sample_option = fields.Selection([('lot_serial', 'Serial No'),('lot', 'Lot No')],string='Sample Type',default='lot')
	down_samp_file = fields.Boolean(string='Download Sample Files')
	

	def import_lots(self):
		if not self.lot_file:
			raise UserError(_("Please upload file first."))
		try:
			fp = tempfile.NamedTemporaryFile(delete=False,suffix=".xlsx")
			fp.write(binascii.a2b_base64(self.lot_file))
			fp.seek(0)
			values = {}
			workbook = xlrd.open_workbook(fp.name)
			sheet = workbook.sheet_by_index(0)
		except Exception:
			raise UserError(_("Invalid file"))
		res = False
		tot = 0.0
		move_lines = self.env['stock.move.line'].search([('move_id','=',self.stock_move_id.id)])
		move_lines.unlink()
		move_active_id = self.env[self._context.get('active_model')].browse(self._context.get('active_id'))
		if self.select_lot == 'serial':
			if sheet.nrows-1 > move_active_id.product_uom_qty:
				raise UserError(_("Your file contains more quantity then initial demand."))
		else:
			for row_no in range(sheet.nrows):
				if row_no <= 0:
					fields = list(map(lambda row:row.value.encode('utf-8'), sheet.row(row_no)))
				else:
					line = list(map(lambda row:isinstance(row.value, bytes) and row.value.encode('utf-8') or str(row.value), sheet.row(row_no)))
					if len(line) == 2:
						tot += float(line[1])
					else:
						raise Warning(_("Format of excel file is inappropriate, Please provide File with proper format."))
			if tot > move_active_id.product_uom_qty:
				raise UserError(_("Your file contains more quantity then initial demand."))
		for row_no in range(sheet.nrows):
			if row_no <= 0:
				fields = list(map(lambda row:row.value.encode('utf-8'), sheet.row(row_no)))
			else:
				try:
					line = list(map(lambda row:isinstance(row.value, bytes) and row.value.encode('utf-8') or str(row.value), sheet.row(row_no)))
					if self.select_lot == 'serial':

						if len(line)==1:
							number =  line[0]
							if number :
								number = number.split(".")	
								number = number[0]

							values.update({'lot':number})
						else:
							raise UserError(_("Format of excel file is inappropriate, Please provide File with proper format.")) 
					else:
						if len(line)==2:
							number =  line[0]
							if number :
								number = number.split(".")	
								number = number[0]
							values.update({'lot':number,'qty':line[1]})
						else:
							raise UserError(_("Format of excel file is inappropriate, Please provide File with proper format."))  
					res = self.create_lot_line(values)
				except IndexError:
					raise UserError(_("You have selected wrong option"))
		view = self.env.ref('stock.view_stock_move_operations')
		stock_pack_id = self.stock_move_id
		if stock_pack_id:
			ctx = dict(
					stock_pack_id.env.context,
					show_lots_m2o=stock_pack_id.has_tracking != 'none' and (stock_pack_id.picking_type_id.use_existing_lots or stock_pack_id.state == 'done' or stock_pack_id.origin_returned_move_id.id),  # able to create lots, whatever the value of ` use_create_lots`.
					show_lots_text=stock_pack_id.has_tracking != 'none' and stock_pack_id.picking_type_id.use_create_lots and not stock_pack_id.picking_type_id.use_existing_lots and stock_pack_id.state != 'done' and not stock_pack_id.origin_returned_move_id.id,
					show_source_location=stock_pack_id.location_id.child_ids,
					show_destination_location=stock_pack_id.location_dest_id.child_ids,
					show_package=not stock_pack_id.location_id.usage == 'supplier',
					show_reserved_quantity=stock_pack_id.state != 'done',
				)
				
			ctx.update({'raise-exception':False})
	
			return {
				'name': _('Detailed Operations'),
				'type': 'ir.actions.act_window',
				'view_type': 'form',
				'view_mode': 'form',
				'res_model': 'stock.move',
				'views': [(view.id, 'form')],
				'view_id': view.id,
				'target': 'new',
				'res_id': stock_pack_id.id,
				'context': ctx
			}
		else:
			return res

	def create_lot_line(self,values):
		list_lot=[]
		lot=values.get('lot')
		stock_pack_id=self.env['stock.move'].browse(self._context.get('active_id'))
		

		if self.select_lot == 'lot' or stock_pack_id.product_id.tracking == 'lot':
			if stock_pack_id.picking_type_id.code == 'incoming' or stock_pack_id.picking_type_id.code == 'internal':
				create_lot = stock_pack_id.picking_type_id.use_create_lots
				existing_lot = stock_pack_id.picking_type_id.use_existing_lots
				if not existing_lot and create_lot:
					lot_vals = {
						'product_id':stock_pack_id.product_id.id,
						'picking_id':stock_pack_id.picking_id.id,
						'qty_done':values.get('qty'),
						'move_id':stock_pack_id.id,
						'lot_name':values.get('lot'),
						'product_uom_id':stock_pack_id.product_id.uom_id.id,
						'location_id':stock_pack_id.picking_id.location_id.id,
						'location_dest_id':stock_pack_id.picking_id.location_dest_id.id,
					}
					self.env['stock.move.line'].with_context({'raise-exception':False}).create(lot_vals)
				elif existing_lot :
					lot_id =self.find_lot(values.get('lot') , stock_pack_id.id)
					if stock_pack_id.picking_type_id.code == 'internal':
						inventory_id=self.env['stock.inventory'].create({'prefill_counted_quantity':'counted'})
						inventory_id.action_start()
						inventory_id.write({'product_ids':[(4,lot_id.product_id.id)]})
						search_line = self.env['stock.inventory.line'].search([('product_id','=',lot_id.product_id.id),('prod_lot_id','=',lot_id.id),('inventory_id','=',inventory_id.id),('location_id','=',stock_pack_id.picking_id.location_id.id)])
						if search_line :
							for inventory_line in search_line :
								inventory_line.write({'product_qty' :values.get('qty')})
						else:

							stock_line_id = self.env['stock.inventory.line'].create({'product_id':lot_id.product_id.id,'prod_lot_id':lot_id.id,'location_id':stock_pack_id.picking_id.location_id.id,'product_qty':values.get('qty'),
																			'inventory_id':inventory_id.id})
							stock_line_id._onchange_quantity_context()
						inventory_id.with_context(lot=True).action_validate()
					lot_vals = {
						'lot_id':lot_id.id,
						'product_id':lot_id.product_id.id,
						'picking_id':stock_pack_id.picking_id.id,
						'qty_done':values.get('qty'),
						'move_id':stock_pack_id.id,
						'lot_name':lot_id.name,
						'product_uom_id':lot_id.product_id.uom_id.id,
						'location_id':stock_pack_id.picking_id.location_id.id,
						'location_dest_id':stock_pack_id.picking_id.location_dest_id.id,
					}                    
					self.env['stock.move.line'].with_context({'raise-exception':False}).create(lot_vals)
		else:
			if lot in list_lot:
				raise Warning('You have already mentioned this lot name in another line')
			else:
				if stock_pack_id.picking_id.picking_type_id.code == 'incoming' or stock_pack_id.picking_type_id.code == 'internal':
					create_lot = stock_pack_id.picking_type_id.use_create_lots
					existing_lot = stock_pack_id.picking_type_id.use_existing_lots
					if not existing_lot and create_lot:
						self.env['stock.move.line'].with_context({'raise-exception':False}).create({
							'qty_done':1,
							'product_id':stock_pack_id.product_id.id,
							'lot_name':values.get('lot'),
							'picking_id':stock_pack_id.picking_id.id,
							'product_uom_id':stock_pack_id.product_id.uom_id.id,
							'move_id':stock_pack_id.id,
							'location_id':stock_pack_id.picking_id.location_id.id,
							'location_dest_id':stock_pack_id.picking_id.location_dest_id.id,

						})
					elif existing_lot :
						lot_id =self.find_lot(values.get('lot'),stock_pack_id.id)
						if stock_pack_id.picking_type_id.code == 'internal':
							inventory_id=self.env['stock.inventory'].create({'prefill_counted_quantity':'counted'})
							inventory_id.action_start()
							inventory_id.write({'product_ids':[(4,lot_id.product_id.id)]})
							search_line = self.env['stock.inventory.line'].search([('product_id','=',lot_id.product_id.id),('prod_lot_id','=',lot_id.id),('inventory_id','=',inventory_id.id),('location_id','=',stock_pack_id.picking_id.location_id.id)])
							if search_line :
								for inventory_line in search_line :
									inventory_line.write({'product_qty' :1.0})

							else :

								stock_line_id = self.env['stock.inventory.line'].create({'product_id':lot_id.product_id.id,'prod_lot_id':lot_id.id,'location_id':stock_pack_id.picking_id.location_id.id,'product_qty':1.0,
																				'inventory_id':inventory_id.id})
								stock_line_id._onchange_quantity_context()
							inventory_id.with_context(lot=True).action_validate()	

						res = self.env['stock.move.line'].with_context({'raise-exception':False}).create({
							'lot_id':lot_id.id,
							'qty_done':1,
							'product_id':lot_id.product_id.id,
							'lot_name':lot_id.name,
							'picking_id':stock_pack_id.picking_id.id,
							'product_uom_id':lot_id.product_id.uom_id.id,
							'move_id':stock_pack_id.id,
							'location_id':stock_pack_id.picking_id.location_id.id,
							'location_dest_id':stock_pack_id.picking_id.location_dest_id.id,
						})
						if stock_pack_id.picking_type_id.code == 'internal':
							res.write({'is_serial':True})

		list_lot.append(lot)

	def find_lot(self,lot , move):
		stock_pack_id=self.env['stock.move'].browse(move)
		lot_details = self.env['stock.production.lot'].search([('name','=', lot), ('product_id','=',stock_pack_id.product_id.id)])


		if not lot_details.id:
			lot_details=self.env['stock.production.lot'].create({
														   'name':lot,
														   'product_id':stock_pack_id.product_id.id,
														   'product_uom_id':stock_pack_id.product_id.uom_id.id,
														   'company_id' : stock_pack_id.company_id.id,
														   })
		return lot_details


	def download_auto(self):
		return {
             'type' : 'ir.actions.act_url',
             'url': '/web/binary/download_document?model=import.lot.wizard&id=%s'%(self.id),
             'target': 'new',
             }


class stock_move(models.Model):
	_inherit = 'stock.move'

	create_exist_lot = fields.Boolean(string="Import Lot/serial with existing lot",
		compute = "_check_import_lot_serial" ,store=True)
	create_lot = fields.Boolean(string="Import New Lot/serial",
		compute = "_check_import_lot_serial" ,store=True)

	@api.depends('picking_id.picking_type_id','picking_id.picking_type_id.use_create_lots' , 'picking_id.picking_type_id.use_existing_lots')
	def _check_import_lot_serial(self):
		for rec in self:
			picking_type = rec.picking_id.picking_type_id
			if picking_type.use_create_lots and picking_type.use_existing_lots:
				rec.update({
					'create_exist_lot': True,
					'create_lot' : False
					})
			elif picking_type.use_create_lots and not picking_type.use_existing_lots:
				rec.update({
					'create_exist_lot': False,
					'create_lot' : True
					})
			else:
				rec.update({
					'create_exist_lot': False,
					'create_lot' : False
					})

	def open_serial_wizard(self):
		view = self.env.ref('import_lot_serial_no.lot_wizard_view')
		ctx = {}   
		ctx.update({'default_stock_move_id':self.id})
		return {
			'name': _('Import Lots'),
			'type': 'ir.actions.act_window',
			'view_mode': 'form',
			'res_model': 'import.lot.wizard',
			'view_id': view.id,
			'target': 'new',
			'context': ctx
		}

	def _update_reserved_quantity(self, need, available_quantity, location_id, lot_id=None, package_id=None, owner_id=None, strict=True):
		""" Create or update move lines.
		"""

		self.ensure_one()

		lots = []
		for line in self.move_line_ids:
			lots.append(line.lot_id.id)
		if lots:
			lot_id = self.env['stock.production.lot'].browse(lots)
		else:
			lot_id = self.env['stock.production.lot']
		if not package_id:
			package_id = self.env['stock.quant.package']
		if not owner_id:
			owner_id = self.env['res.partner']

		taken_quantity = min(available_quantity, need)

		# `taken_quantity` is in the quants unit of measure. There's a possibility that the move's
		# unit of measure won't be respected if we blindly reserve this quantity, a common usecase
		# is if the move's unit of measure's rounding does not allow fractional reservation. We chose
		# to convert `taken_quantity` to the move's unit of measure with a down rounding method and
		# then get it back in the quants unit of measure with an half-up rounding_method. This
		# way, we'll never reserve more than allowed. We do not apply this logic if
		# `available_quantity` is brought by a chained move line. In this case, `_prepare_move_line_vals`
		# will take care of changing the UOM to the UOM of the product.
		if not strict and self.product_id.uom_id != self.product_uom:
			taken_quantity_move_uom = self.product_id.uom_id._compute_quantity(taken_quantity, self.product_uom, rounding_method='DOWN')
			taken_quantity = self.product_uom._compute_quantity(taken_quantity_move_uom, self.product_id.uom_id, rounding_method='HALF-UP')

		quants = []
		rounding = self.env['decimal.precision'].precision_get('Product Unit of Measure')

		if self.product_id.tracking == 'serial':
			if float_compare(taken_quantity, int(taken_quantity), precision_digits=rounding) != 0:
				taken_quantity = 0

		try:
			with self.env.cr.savepoint():
				if not float_is_zero(taken_quantity, precision_rounding=self.product_id.uom_id.rounding):
					quants = self.env['stock.quant']._update_reserved_quantity(
						self.product_id, location_id, taken_quantity, lot_id=lot_id,
						package_id=package_id, owner_id=owner_id, strict=strict
					)
		except UserError:
			taken_quantity = 0

		# Find a candidate move line to update or create a new one.
		for reserved_quant, quantity in quants:
			to_update = self.move_line_ids.filtered(lambda ml: ml._reservation_is_updatable(quantity, reserved_quant))
			if to_update:
				uom_quantity = self.product_id.uom_id._compute_quantity(quantity, to_update[0].product_uom_id, rounding_method='HALF-UP')
				uom_quantity = float_round(uom_quantity, precision_digits=rounding)
				uom_quantity_back_to_product_uom = to_update[0].product_uom_id._compute_quantity(uom_quantity, self.product_id.uom_id, rounding_method='HALF-UP')
			if to_update and float_compare(quantity, uom_quantity_back_to_product_uom, precision_digits=rounding) == 0:
				to_update[0].with_context(bypass_reservation_update=True).product_uom_qty += uom_quantity
			else:
				if self.product_id.tracking == 'serial':
					for i in range(0, int(quantity)):
						self.env['stock.move.line'].create(self._prepare_move_line_vals(quantity=1, reserved_quant=reserved_quant))
				else:
					self.env['stock.move.line'].create(self._prepare_move_line_vals(quantity=quantity, reserved_quant=reserved_quant))
		return taken_quantity
					
				
class PickingTypeInherit(models.Model):
	_inherit = "stock.picking.type"
	
	def _get_action(self, action_xmlid):
		action = self.env.ref(action_xmlid).read()[0]
		if self:
			action['display_name'] = self.display_name
		context = {
			'search_default_picking_type_id': [self.id],
			'default_picking_type_id': self.id,
			'default_company_id': self.company_id.id,
		}
		action_context = literal_eval(action['context'])
		context = {**action_context, **context}
		action['context'] = context
		return action    




class Stockquant_inherit(models.Model):
	_inherit = "stock.quant"


	def _gather(self, product_id, location_id, lot_id=None, package_id=None, owner_id=None, strict=False):
		

		self.env['stock.quant'].flush(['location_id', 'owner_id', 'package_id', 'lot_id', 'product_id'])
		self.env['product.product'].flush(['virtual_available'])
		removal_strategy = self._get_removal_strategy(product_id, location_id)
		removal_strategy_order = self._get_removal_strategy_order(removal_strategy)
		domain = [
			('product_id', '=', product_id.id),
		]
		if not strict:
			if lot_id and len(lot_id) == 1:
				domain = expression.AND([['|', ('lot_id', '=', lot_id.id), ('lot_id', '=', False)], domain])
			if lot_id and len(lot_id) > 1:
				domain = expression.AND([['|', ('lot_id', 'in', lot_id.ids), ('lot_id', '=', False)], domain])
			if package_id:
				domain = expression.AND([[('package_id', '=', package_id.id)], domain])
			if owner_id:
				domain = expression.AND([[('owner_id', '=', owner_id.id)], domain])
			domain = expression.AND([[('location_id', 'child_of', location_id.id)], domain])
		else:
			if lot_id and len(lot_id) == 1:
				domain = expression.AND([['|', ('lot_id', '=', lot_id.id), ('lot_id', '=', False)] if lot_id else [('lot_id', '=', False)], domain])
			if lot_id and len(lot_id) > 1:
				domain = expression.AND([['|', ('lot_id', 'in', lot_id.ids), ('lot_id', '=', False)] if lot_id else [('lot_id', '=', False)], domain])
			domain = expression.AND([[('package_id', '=', package_id and package_id.id or False)], domain])
			domain = expression.AND([[('owner_id', '=', owner_id and owner_id.id or False)], domain])
			domain = expression.AND([[('location_id', '=', location_id.id)], domain])
		# Copy code of _search for special NULLS FIRST/LAST order
		self.check_access_rights('read')
		query = self._where_calc(domain)
		self._apply_ir_rules(query, 'read')
		from_clause, where_clause, where_clause_params = query.get_sql()
		where_str = where_clause and (" WHERE %s" % where_clause) or ''
		query_str = 'SELECT "%s".id FROM ' % self._table + from_clause + where_str + " ORDER BY "+ removal_strategy_order
		self._cr.execute(query_str, where_clause_params)
		res = self._cr.fetchall()
		# No uniquify list necessary as auto_join is not applied anyways...
		quants = self.browse([x[0] for x in res])
		quants = quants.sorted(lambda q: not q.lot_id)
		return quants

class Stockmove_inherit(models.Model):
	_inherit = "stock.move.line"

	is_serial = fields.Boolean(string="serial or not")

	def _reservation_is_updatable(self, quantity, reserved_quant):
		self.ensure_one()
		if self.is_serial == True:
			if (self.location_id.id == reserved_quant.location_id.id and
					self.lot_id.id == reserved_quant.lot_id.id and
					self.package_id.id == reserved_quant.package_id.id and
					self.owner_id.id == reserved_quant.owner_id.id):
				return True

			return False
		else:
			return super(Stockmove_inherit,self)._reservation_is_updatable(quantity=quantity,reserved_quant=reserved_quant)


# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
