from odoo import fields, models

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    elevenlabs_api_key = fields.Char(
        string="ElevenLabs API Key", 
        config_parameter='voice_to_text.api_key',
    )
    elevenlabs_voice_id = fields.Char(
        string="ElevenLabs Voice ID", 
        config_parameter='voice_to_text.voice_id',
    )
    groq_api_key = fields.Char(
        string="Groq API Key", 
        config_parameter='voice_to_text.groq_key',
    )
