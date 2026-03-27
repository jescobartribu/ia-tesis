import logging
from odoo import http
from odoo.http import request, Response
import json
from difflib import SequenceMatcher

_logger = logging.getLogger(__name__)

class SimpleApiController(http.Controller):

    @http.route('/api/auth/test', type="http", auth="public", methods=["GET", "OPTIONS"], csrf=False)
    def test_auth(self, **kwargs):
        # 1. Manejo de CORS (necesario para APIs externas)
        if request.httprequest.method == 'OPTIONS':
            return request.make_response('', headers=[
                ('Access-Control-Allow-Origin', '*'),
                ('Access-Control-Allow-Headers', 'Authorization, Content-Type')
            ])

        # 2. Obtener Token del header
        auth_header = request.httprequest.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return request.make_json_response({"error": "No token provided"}, status=401)
        
        token = auth_header.split(" ", 1)[1]

        # 3. Validar con Odoo API Keys
        user_id = request.env["res.users.apikeys"]._check_credentials(scope="rpc", key=token)
        
        if not user_id:
            return request.make_json_response({"error": "Invalid token"}, status=401)

        user = request.env["res.users"].sudo().browse(user_id)
        return request.make_json_response({
            "status": "success",
            "user": user.name
        })

    def _check_bearer_auth(self):
        """Método privado para validar el token Bearer con las API Keys de Odoo"""
        auth_header = request.httprequest.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return None
        
        token = auth_header.split(" ", 1)[1]
        user_id = request.env["res.users.apikeys"]._check_credentials(scope="rpc", key=token)
        return user_id


    @http.route('/api/check_patient', type="json", auth="public", methods=["POST"], csrf=False)
    def check_patient(self, **kwargs):
        _logger.info("HEADERS RECIBIDOS")
        _logger.info(request.httprequest.headers)
        
        # Extraer el token manualmente para probar
        auth_header = request.httprequest.headers.get('Authorization')
        _logger.info("Token recibido: %s", auth_header)
        _logger.info("INFO")
        _logger.info(kwargs)
        user_id = self._check_bearer_auth()
        if not user_id:
            return {"status": "error", "message": "Invalid or missing Bearer Token"}

        vat = kwargs.get('cedula')
        
        if not vat:
            return {"status": "error", "message": "Debe proporcionar una cédula"}

        patient = request.env['hms.patient'].sudo().search([('vat', '=', str(vat))], limit=1)
        _logger.info("Patient: %s", patient)
        if patient:
            return {
                "exists": True,
                "patient_data": {
                    "id": patient.id,
                    "name": patient.name,
                    "email": patient.email or "",
                    "phone": patient.phone or "",
                    "birthday": str(patient.birthday) if patient.birthday else "",
                    "gender": patient.gender or "",
                }
            }
        else:
            return {
                "exists": False,
                "message": "Paciente no encontrado"
            }

    @http.route('/api/create_patient', type="json", auth="public", methods=["POST"], csrf=False)
    def create_patient(self, **kwargs):
        # 1. Verificación de Seguridad
        user_id = self._check_bearer_auth()
        if not user_id:
            return {"status": "error", "message": "Unauthorized"}

        _logger.info("********** CREANDO/BUSCANDO PACIENTE **********")
        _logger.info("Datos recibidos: %s", kwargs)

        # 3. Extraer datos del paciente
        cedula = kwargs.get('vat')
        name = kwargs.get('name')
        
        if not cedula or not name:
            return {"status": "error", "message": "Faltan campos obligatorios: vat y name"}

        patient_model = request.env['hms.patient'].sudo()

        try:
            patient = patient_model.create({
                'name': name,
                'vat': str(cedula),
                'email': kwargs.get('email'),
                'phone': kwargs.get('phone'),
                'gender': kwargs.get('gender'),
            })
            action = "created"

            return {
                "status": "success",
                "action": action,
                "patient_id": patient.id,  
                "name": patient.name
            }

        except Exception as e:
            _logger.error("Error al procesar paciente: %s", str(e))
            return {"status": "error", "message": str(e)}
        
    @http.route('/api/recipe', type="json", auth="public", methods=["POST"], csrf=False)
    def prueba(self, **kwargs):        
        
        name = kwargs.get('name', 'no')
        
        # Creamos el patient
        patient = request.env['hms.appointment'].sudo().create({
            'patient_id': patient_id,
            'name': case,
            'date': date
        })
        
        return {"status": "success", "id": patient.id}