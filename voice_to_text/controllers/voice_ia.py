import requests
import json
from odoo import http
from odoo.http import request

class VoiceIA(http.Controller):

    @http.route('/fenix/get_audio', type='json', auth='user')
    def get_elevenlabs_audio(self, text):
        api_key = "30faffafdbc1665632c96c7fa6a6462fcb5b11d43c1dace683ab041c8fbb4cd9"
        voice_id = "pNInz6obpgDQGcFmaJgB" # Voz de Adam (Estándar)
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"

        headers = {
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
            "xi-api-key": api_key
        }

        data = {
            "text": text,
            "model_id": "eleven_turbo_v2_5", # Más rápido y ligero
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.5}
        }

        try:
            response = requests.post(url, json=data, headers=headers)
            if response.status_code == 200:
                # Retornamos el audio en base64 para que OWL lo reproduzca
                import base64
                return base64.b64encode(response.content).decode('utf-8')
            else:
                return {"error": f"Error de API: {response.status_code}"}
        except Exception as e:
            return {"error": str(e)}