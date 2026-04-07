from odoo import models, fields, api

class IADisaggregateWizard(models.TransientModel):
    _name = 'ia.disaggregate.wizard'
    _description = 'Asistente de Disgregación IA'

    # Campos para que el usuario confirme
    config_id = fields.Many2one('voice.disaggregation.config', string="Configuración a usar", required=True)
    source_text = fields.Text(string="Texto a Procesar", readonly=True)
    res_model = fields.Char(string="Modelo Destino")
    res_id = fields.Integer(string="ID del Registro")

    def action_confirm_disaggregate(self):
        """ Ejecuta la IA y aplica los cambios al registro original """
        self.ensure_one()
        record = self.env[self.res_model].browse(self.res_id)
        
        # Esta llamada ahora es dinámica y usa tu lógica de Groq
        extracted_data = self.env['voice.command.config']._ai_parse_disaggregation(
            self.source_text, 
            self.config_id
        )
        
        if extracted_data:
            record.write(extracted_data)
                
        return {'type': 'ir.actions.act_window_close'}