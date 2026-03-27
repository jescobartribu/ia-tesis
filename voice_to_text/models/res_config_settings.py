from odoo import fields, models

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    elevenlabs_api_key = fields.Char(
        string="ElevenLabs API Key", 
        config_parameter='voice_to_text.api_key',
        default="sk_457256bc75061df22057af4c64c39e82f5326a7af54cafaa"
    )
    elevenlabs_voice_id = fields.Char(
        string="ElevenLabs Voice ID", 
        config_parameter='voice_to_text.voice_id',
        default="pNInz6obpgDQGcFmaJgB"
    )
    groq_api_key = fields.Char(
        string="Groq API Key", 
        config_parameter='voice_to_text.groq_key',
        default="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"
    )
