from odoo import models, fields, api, _

class VoiceDisaggregationConfig(models.Model):
    _name = 'voice.disaggregation.config'
    _description = 'Configuración de Disgregación Irene IA'

    name = fields.Char(string='Nombre del Botón', required=True, default="Disgregar con IA")
    model_id = fields.Many2one(
        'ir.model', 
        string='Modelo Destino', 
        required=True, 
        ondelete='cascade'
    )
    model_name = fields.Char(related='model_id.model', readonly=True)
    
    # Vista donde se inyectará el botón (ej: hms.patient.form)
    inherit_id = fields.Many2one(
        'ir.ui.view', 
        string='Vista Padre', 
        domain="[('model', '=', model_name), ('type', '=', 'form'), ('inherit_id', '=', False)]",
        required=True,
        ondelete='cascade'
    )
    
    view_id = fields.Many2one(
        'ir.ui.view', 
        string='Vista de Botón Generada', 
        readonly=True,
        ondelete='set null' # Si se borra la vista generada, el campo queda vacío
    )
    
    field_id = fields.Many2one(
        'ir.model.fields', 
        string="Campo Origen (Relato)",
        domain="[('model_id', '=', model_id), ('ttype', 'in', ['text', 'html'])]", 
        required=True,
        ondelete='cascade'
    )

    # Relación con los campos que la IA debe llenar
    line_ids = fields.One2many('voice.disaggregation.line', 'config_id', string="Campos a Extraer")

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            rec._create_or_update_button_view()
        return records

    def write(self, vals):
        res = super().write(vals)
        if any(k in vals for k in ['name', 'inherit_id', 'model_id']):
            self._create_or_update_button_view()
        return res

    def unlink(self):
        views_to_delete = self.mapped('view_id')
        res = super().unlink()
        views_to_delete.unlink()
        return res

    def _create_or_update_button_view(self):
        for rec in self:
            arch_xml = f"""
                <xpath expr="//header" position="inside">
                    <button name="action_open_ia_disaggregate_wizard" 
                            type="object" 
                            string="{rec.name}" 
                            class="btn-secondary"
                            context="{{'active_config_id': {rec.id}}}"/>
                </xpath>
            """
            if rec.view_id:
                rec.view_id.write({'arch': arch_xml, 'inherit_id': rec.inherit_id.id})
            else:
                new_view = self.env['ir.ui.view'].create({
                    'name': f'IA_Btn_{rec.model_name}_{rec.id}',
                    'type': 'form',
                    'model': rec.model_name,
                    'mode': 'extension',
                    'inherit_id': rec.inherit_id.id,
                    'arch': arch_xml,
                })
                rec.view_id = new_view.id

class VoiceDisaggregationLine(models.Model):
    _name = 'voice.disaggregation.line'
    config_id = fields.Many2one('voice.disaggregation.config')
    field_id = fields.Many2one('ir.model.fields', string="Campo Destino")
    instruction = fields.Char("Instrucción IA", help="Ej: 'Extrae enfermedades'")