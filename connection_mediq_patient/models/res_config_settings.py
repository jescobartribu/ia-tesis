from odoo import fields, models

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    external_api_url = fields.Char(
        string="URL del Sistema Externo", 
        config_parameter='connection_mediq.external_url',
        default="http://143.198.73.129:17001"
    )
    external_api_token = fields.Char(
        string="Token de Integración", 
        config_parameter='connection_mediq.external_token'
    )