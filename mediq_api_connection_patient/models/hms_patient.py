import requests
import logging
from odoo import models, fields, api
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class HmsPatient(models.Model):
    _inherit = 'hms.patient'

    mediq_id = fields.Char(string="ID Mediq", copy=False, index=True)

    def action_send_to_external_system(self):
        self.ensure_one()
        user_bot = self.env['res.users'].sudo().search([('login', '=', 'pruebamediq@gmail.com')], limit=1)

        if not user_bot or not user_bot.token_external:
            raise UserError("No se ha configurado el token externo para el usuario.")

        token = user_bot.token_external

        url = "http://143.198.73.129:17000/api/create_patient"
        # token = "c78f19fe569447d62417bc43107e8d229f9e9ad8"
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "params": {
                "name": self.name,
                "vat": self.vat,
                "email": self.email or "",
                "phone": self.phone or "",
                "gender": self.gender or "",
            }
        }

        try:
            _logger.info("Enviando paciente %s al sistema externo", self.name)
            response = requests.post(url, json=payload, headers=headers, timeout=10)
            response.raise_for_status()
            
            res_data = response.json().get('result', {})
            
            if res_data.get('status') == 'success':
                external_id = res_data.get('patient_id')
                return {
                    'effect': {
                        'fadeout': 'slow',
                        'message': f"Paciente sincronizado con éxito. ID Externo: {external_id}",
                        'type': 'rainbow_man',
                        # 'img_url': '/voice_to_text/static/description/logo.png', 
                    }
                }
            else:
                raise UserError(f"Error del servidor externo: {res_data.get('message')}")

        except Exception as e:
            _logger.error("Fallo al sincronizar: %s", str(e))
            raise UserError(f"No se pudo conectar con el sistema externo: {str(e)}")

    