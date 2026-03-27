from odoo import models, fields, api
import requests
import json
import logging

_logger = logging.getLogger(__name__)

class VoiceCommandConfig(models.Model):
    _name = 'voice.command.config'
    _description = 'Configuración de Comandos de Voz Dinámicos'

    name = fields.Char(string="Nombre del Comando", required=True, help="Ej: Crear Paciente")
    
    # El modelo de Odoo sobre el que actuará (ej: res.partner, product.product)
    model_id = fields.Many2one('ir.model', string="Modelo Destino")
    model_name = fields.Char(related='model_id.model', string="Nombre Técnico del Modelo")

    prueba = fields.Text()

    # Palabras que disparan este comando
    trigger_words = fields.Char(
        string="Palabras Clave", 
        help="Palabras separadas por coma que activan este modelo. Ej: paciente, cliente, persona"
    )

    # Tipo de acción
    action_type = fields.Selection([
        ('create', 'Crear Registro'),
        ('filter', 'Filtrar Vista'),
        ('search', 'Solo Buscar')
    ], string="Acción", default='create', required=True)

    field_config_ids = fields.One2many(
        'voice.command.config.line', 
        'parent_id', 
        string="Configuración de Campos"
    )

    active = fields.Boolean(default=True)

    def get_config_for_ai(self):
        """ Retorna la configuración en formato simple para enviársela a la IA """
        configs = self.search([('active', '=', True)])
        res = []
        for config in configs:
            res.append({
                'trigger': config.trigger_words,
                'model': config.model_name,
                'action': config.action_type,
                'fields': config.field_config_ids.mapped('field_id.name'),
                'fields_ia': config.field_config_ids.mapped('name_ia')
            })
        return res
    
    def action_IA_complete(self):
        self.ensure_one()
        if not self.prueba:
            return
            
        url = "https://api.groq.com/openai/v1/chat/completions"
        api_key = "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"
        
        payload = {
            "model": "llama-3.1-8b-instant",
            "messages": [
                {"role": "system", "content": "Eres un asistente técnico."},
                {"role": "user", "content": f"Estructura esto: {self.prueba}"}
            ]
        }
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=10)
            result = response.json()
            ai_text = result['choices'][0]['message']['content']
            
            # Escribimos el resultado directamente en el campo
            self.prueba = ai_text
        except Exception as e:
            # Esto sacará un mensaje en la UI de Odoo si algo falla
            raise models.ValidationError(f"Error de IA: {str(e)}")

    @api.model
    def voice_create_record(self, model_name, values):
        """
        Busca IDs para campos Many2one y crea el registro.
        """
        final_vals = {}
        # Obtener la configuración de las líneas para este modelo
        config = self.search([('model_id.model', '=', model_name)], limit=1)
        
        for field_name, value in values.items():
            # Buscar si este campo es un Many2one en la configuración
            line = config.field_config_ids.filtered(lambda l: l.name == field_name)
            
            if line and line.ttype == 'many2one':
                # Buscamos el ID en el modelo relacionado (ej. hms.patient)
                target_model = line.field_id.relation
                # record = self.env[target_model].search([('display_name', 'ilike', value)])
                record = self.env[target_model].search([('name', '=ilike', value.strip())], limit=1)
                _logger.info("Buscando paciente con nombre: %s", value)
                if record:
                    final_vals[field_name] = record.id
                else:
                    # Si no existe, lo creamos (opcional según tu flujo)
                    new_rec = self.env[target_model].create({'name': value})
                    final_vals[field_name] = new_rec.id
            else:
                final_vals[field_name] = value

        # Crear el registro final con los IDs correctos
        new_record = self.env[model_name].create(final_vals)
        return new_record.id

class VoiceCommandConfigLine(models.Model):
    _name = 'voice.command.config.line'
    _description = ''

    parent_id = fields.Many2one('voice.command.config', ondelete='cascade')
    
    field_id = fields.Many2one(
        'ir.model.fields', 
        string="Campo",
        required=True,
        ondelete='cascade',
        domain="[('model_id', '=', parent_model_id), ('ttype', 'not in', ['one2many', 'reference'])]"
    )
    
    field_description = fields.Char(related='field_id.field_description', readonly=True)
    name = fields.Char(related='field_id.name', readonly=True)
    ttype = fields.Selection(related='field_id.ttype', readonly=True)

    name_ia = fields.Char(string="Nombre IA")    
    parent_model_id = fields.Many2one(related='parent_id.model_id')

