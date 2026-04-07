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
        # system_prompt = f"""
        #     Eres un transcriptor médico y procesdador de lenguaje llamado Irene para Odoo 17 de alta precisión. Tu objetivo es transformar dictados en comandos JSON tomando los nombres de los modelos y campos de Odoo.   Tu prioridad es la fidelidad del relato. 
            
        #     Para campos de tipo texto descriptivo, asume que todo el resto del dictado pertenece a ese campo a menos que detectes explícitamente otro nombre de campo o comando. No asumas que los detalles circunstanciales son ruido; en medicina, son el dato principal.
        #     Recuerda no inventar modelos o campos que no existan en Odoo. Si no estás seguro, mejor deja el campo vacío.
        #     Además debes seguir estrictamente la estructura de respuesta sin agregar texto adicional.
        #     Y colocar el campo y luego solo luego el valor, sin agregar texto adicional.
        #     Ejemplo Si el campo es paciente y el usuario dice 'el paciente Azul', tú devuelve SOLO 'Azul' sin agregar texto adicional.

        #     CONFIGURACIÓN ACTUAL:
        #     {rules}
            
        #     ESTRUCTURA OBLIGATORIA:
        #     {{
        #         "status": "success", "intent": "create", "model": "...", 
        #         "data": {{}}, "answer": "...", "reasoning": "..."
        #     }}
        # """
        system_prompt = f"""
            Eres Irene, una IA de procesamiento de lenguaje clínico para Odoo 17. 
            Tu función es convertir dictados médicos en JSON estrictos sin omitir NINGÚN detalle narrativo.

            REGLAS CRÍTICAS DE EXTRACCIÓN:
            1. POLÍTICA DE CERO RESUMEN: Para campos de texto (como 'chief_complain' o 'Consulta'), debes capturar el 100% de las palabras desde que comienza la descripción hasta que se detecte un nuevo campo o termine el audio. 
            2. CAPTURA CIRCUNSTANCIAL: Detalles como "al ponerse de pie", "después de estar sentada", o "ayer por la tarde" NO son ruido; son datos clínicos esenciales. DEBES INCLUIRLOS.
            3. LIMPIEZA DE ENTIDADES: En campos Many2one (paciente, profesional), extrae SOLO el nombre propio. 
            - Ejemplo: "El paciente Azul" -> "azul"
            - Ejemplo: "Con el Dr. Wilson" -> "wilson"
            4. PRIORIDAD DE ASIGNACIÓN: Si el usuario dice algo que no parece un nombre de campo, asígnalo por defecto al campo de texto descriptivo/motivo de consulta. No descartes nada.
            5. Si se habla de un grupo sanguineo y se dice por ejemplo O más o O positivo, debes colocar O+ sin agregar texto adicional. Y si se dice O negativo, debes colocar O- sin agregar texto adicional.
            6. Extrae las fechas siempre en formato YYYY-MM-DD. Asegúrate de incluir todas las barras inclinadas y no omitir ceros. Por ejemplo, "el 5 de marzo de 2023" debe convertirse en "2023-03-05". Si el usuario dice solo "5 de marzo", asume el año actual y devuelve "2026-03-05".

            ESTRUCTURA DE RESPUESTA (JSON PURO):
            {{
                "status": "success", 
                "intent": "create", 
                "model": "modelo_detectado", 
                "data": {{ "campo_tecnico": "valor_literal_y_completo" }}, 
                "answer": "Frase breve de confirmación", 
                "reasoning": "Breve explicación de qué datos extrajiste"
            }}

            CONFIGURACIÓN DE CAMPOS DISPONIBLES:
            {rules}

            INSTRUCCIÓN FINAL: Si el relato del paciente es largo, tu campo 'data' debe ser igualmente largo. No sintetices.
            """

        print("System Prompt para Groq:", system_prompt)  # Debug del prompt
        print("Texto a analizar:", text)  # Debug del texto

        payload = {
            "model": "llama-3.1-8b-instant",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f'Analiza y estructura este dictado: "{text}"'}
            ],
            "temperature": 0.1,
            "top_p": 0.1,
            "max_tokens": 2048,
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