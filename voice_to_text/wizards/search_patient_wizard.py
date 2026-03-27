import requests
import json
import logging
from odoo import models, fields, api
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class SearchPatientWizard(models.TransientModel):
    _name = 'search.patient.wizard'
    _description = 'Consultar Paciente en Sistema Externo'

    vat = fields.Char(string='Cédula a Consultar', required=True)

    def action_search_external(self):
        self.ensure_one()
        user_bot = self.env['res.users'].sudo().search([('login', '=', 'pruebamediq@gmail.com')], limit=1)

        if not user_bot or not user_bot.token_external:
            raise UserError("No se ha configurado el token externo para el usuario de integración.")

        token = user_bot.token_external
        
        url = "http://143.198.73.129:17000/api/check_patient"
        # token = "c78f19fe569447d62417bc43107e8d229f9e9ad8" 
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "params": {
                "cedula": self.vat
            }
        }

        try:
            _logger.info("Consultando cédula %s en sistema externo", self.vat)
            response = requests.post(url, json=payload, headers=headers, timeout=10)
            response.raise_for_status() # Lanza error si el HTTP status es 4xx o 5xx
            
            response_json = response.json()
            _logger.info("RESPUESTA COMPLETA DEL SERVIDOR: %s", response_json)
            res_data = response.json().get('result', {})
            _logger.info("RESPUESTA REST_DATA DEL SERVIDOR: %s", res_data)
            _logger.info("RESPUESTA EXIST DEL SERVIDOR: %s", res_data.get('exists'))


            if res_data.get('exists'):
                patient_info = res_data.get('patient_data')
                                
                vals = {
                    'name': patient_info.get('name'),
                    'vat': self.vat,
                    'email': patient_info.get('email'),
                    'phone': patient_info.get('phone'),
                }
                patient_local = self.env['hms.patient'].sudo().create(vals)
                
                return {
                    'type': 'ir.actions.act_window',
                    'res_model': 'hms.patient',
                    'res_id': patient_local.id,
                    'view_mode': 'form',
                    'target': 'current',
                }
            else:
                raise UserError("El paciente no existe en el sistema externo.")

        except requests.exceptions.RequestException as e:
            _logger.error("Error de conexión con Odoo Externo: %s", str(e))
            raise UserError(f"No se pudo conectar con el servidor externo: {str(e)}")