import requests
import json
from odoo import http
from odoo.http import request

class groqIA(http.Controller):

    @http.route('/groq/process_command', type='json', auth='user')
    def process_ai_command(self, text, rules):
        # 1. Obtener la API Key de los parámetros del sistema
        icp = request.env['ir.config_parameter'].sudo()
        api_key = icp.get_param('voice_to_text.groq_key')
        
        if not api_key:
            return {"status": "error", "reasoning": "API Key de Groq no configurada"}

        url = "https://api.groq.com/openai/v1/chat/completions"
        
        # 2. Construir el System Prompt (puedes mover la lógica pesada aquí)
        system_prompt = f"""
            Eres un procesador de lenguaje natural llamado Irene para Odoo 17.
            Tu objetivo es transformar dictados en comandos JSON.
            
            CONFIGURACIÓN ACTUAL:
            {rules}
            
            ESTRUCTURA OBLIGATORIA:
            {{
                "status": "success", "intent": "create", "model": "...", 
                "data": {{}}, "answer": "...", "reasoning": "..."
            }}
        """

        payload = {
            "model": "llama-3.1-8b-instant",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f'Analiza y estructura este dictado: "{text}"'}
            ],
            "response_format": {"type": "json_object"}
        }

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        try:
            response = requests.post(url, json=payload, headers=headers, timeout=10)
            if response.status_code == 200:
                result = response.json()
                # Retornamos el contenido del mensaje ya parseado
                return json.loads(result['choices'][0]['message']['content'])
            else:
                return {"status": "error", "reasoning": f"Error Groq: {response.status_code}"}
        except Exception as e:
            return {"status": "error", "reasoning": str(e)}