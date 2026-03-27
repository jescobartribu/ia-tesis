from odoo import api, fields, models

class IrModelFields(models.Model):
    _inherit = 'ir.model.fields'

    name_ia = fields.Char(string="Nombre IA", help="Nombre con lo que te captaran el audio")
    