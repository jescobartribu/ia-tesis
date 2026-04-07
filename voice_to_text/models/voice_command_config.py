from odoo import models, fields, api
import requests
import json
import logging
import re
from dateutil import parser
from odoo.tools.safe_eval import safe_eval, wrap_module
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

class VoiceCommandConfig(models.Model):
    _name = 'voice.command.config'
    _description = 'Configuración de Comandos de Voz Dinámicos'

    name = fields.Char(string="Nombre del Comando", required=True, help="Ej: Crear Paciente")
    
    model_id = fields.Many2one('ir.model', string="Modelo Destino")
    model_name = fields.Char(related='model_id.model', string="Nombre Técnico del Modelo")

    # Código que se ejecuta ANTES de crear (para validar o buscar en otros sistemas)
    pre_python_logic = fields.Text(
        string="Lógica Pre-Ejecución",
        help="Variables disponibles: values (dict), env, model, user. "
             "Puedes modificar 'values' o lanzar validaciones."
    )

    # Código que se ejecuta DESPUÉS de crear
    post_python_logic = fields.Text(
        string="Lógica Post-Ejecución",
        help="Variables disponibles: record (el objeto creado), env, values."
    )

    # Palabras que disparan este comando
    trigger_words = fields.Char(
        string="Palabras Clave", 
        help="Palabras separadas por coma que activan este modelo. Ej: paciente, cliente, persona"
    )

    # Tipo de acción
    action_type = fields.Selection([
        ('create', 'Crear Registro'),
        ('filter', 'Filtrar Vista'),
        ('search', 'Solo Buscar'),
        ('edit', 'Editar Registro')
    ], string="Acción", default='create', required=True)

    field_config_ids = fields.One2many(
        'voice.command.config.line', 
        'parent_id', 
        string="Configuración de Campos"
    )

    active = fields.Boolean(default=True)

    def _prepare_final_values(self, config, values):
        """ 
        Procesa el diccionario de la IA validando rangos, mapeando selecciones 
        y resolviendo relaciones Many2one según la configuración de las líneas.
        """
        final_vals = {}
        for field_name, value in values.items():
            # Buscamos la configuración específica para este campo técnico
            line = config.field_config_ids.filtered(lambda l: l.name == field_name)
            
            if not line:
                final_vals[field_name] = value
                continue

            # 1. VALIDACIÓN DE RANGOS (Números, Monedas)
            if line.ttype in ['integer', 'float', 'monetary'] and line.has_range:
                val_num = float(value or 0)
                if val_num < line.min_value or val_num > line.max_value:
                    raise ValidationError(
                        f"El campo {line.field_description} ({val_num}) está fuera de rango "
                        f"[{line.min_value} - {line.max_value}]."
                    )
            # elif line.ttype in ['date', 'datetime']:
            #     try:
            #         val_norm = str(value).lower().strip()
            #         val_clean = val_norm.replace('fecha:', '').strip()
            #         hoy = datetime.now()
            #         target_date = None

            #         # --- MAPEOS DE LENGUAJE NATURAL ---
            #         if 'hoy' in val_norm:
            #             target_date = hoy
            #         elif 'ayer' in val_norm:
            #             target_date = hoy - timedelta(days=1)
            #         elif 'mañana' in val_norm and 'pasado' not in val_norm:
            #             target_date = hoy + timedelta(days=1)
            #         elif 'pasado mañana' in val_norm:
            #             target_date = hoy + timedelta(days=2)
                    
            #         # --- SI ES UNA FECHA ESPECÍFICA (Ej: "15 de mayo") ---
            #         if not target_date:
            #             try:
            #                 # Intentamos parsear formatos estándar que la IA suele enviar
            #                 # "2026-04-15" o "15/04/2026"
            #                 target_date = Date.from_string(value)
            #             except:
            #                 try:
            #                     # Si falla, intentamos el formato que te dio el error (DD/MM/YYYY)
            #                     target_date = datetime.strptime(val_clean, '%分/%m/%Y')
            #                 except ValueError:
            #                     _logger.warning("Irene: No se pudo parsear fecha '%s'", val_clean)
            #                 _logger.warning("Irene: No se pudo parsear la fecha directamente: %s", value)
                    
            #         if target_date:
            #             if line.ttype == 'date':
            #                 final_vals[field_name] = target_date.strftime('%Y-%m-%d')
            #             else:
            #                 # Para datetime, por defecto ponemos las 08:00 AM si no hay hora
            #                 final_vals[field_name] = target_date.strftime('%Y-%m-%d 08:00:00')
            #         else:
            #             # Si todo falla, dejamos que Odoo intente lo que mandó la IA
            #             final_vals[field_name] = value

            #     except Exception as e:
            #         _logger.error("Error procesando fecha: %s", str(e))
            
            elif line.ttype in ['date', 'datetime']:
                try:
                    # Limpiamos el valor (ej: "3/5/2026" o "03-05-2026")
                    val_clean = str(value).strip().lower()
                    
                    # 1. Intentamos usar el parser inteligente
                    # dayfirst=True le dice que en caso de duda (01/02), el 01 es el día.
                    # fuzzy=True ignora texto basura alrededor de la fecha.
                    try:
                        dt_obj = parser.parse(val_clean, dayfirst=True, fuzzy=True)
                        print(f"Fecha parseada por dateutil: {dt_obj} a partir de '{val_clean}'")
                    except (ValueError, OverflowError):
                        _logger.warning("Irene: No se pudo parsear la fecha con dateutil: %s", val_clean)
                        dt_obj = None

                    if dt_obj:
                        if line.ttype == 'date':
                            # Formateamos al estándar ISO que Odoo SÍ acepta: YYYY-MM-DD
                            final_vals[field_name] = dt_obj.strftime('%Y-%m-%d')
                            print(f"Campo {field_name} procesado como fecha: {final_vals[field_name]}")
                        else:
                            # Para datetime, mantenemos la hora si el parser la encontró
                            final_vals[field_name] = dt_obj.strftime('%Y-%m-%d %H:%M:%S')
                    else:
                        # Si no hay forma de entender la fecha, mejor no enviarla para no romper el create
                        print(f"No se pudo entender la fecha para el campo {field_name}, valor original: '{value}'")
                        continue 

                except Exception as e:
                    _logger.error("Error crítico procesando fecha en %s: %s", field_name, str(e))
            # elif line.ttype == 'selection':
            #     try:
            #         # EXTRAER MODELO DESDE EL CAMPO (Solución al AttributeError)
                    
            #         model_technical_name = line.field_id.model_id.model
                    
            #         # Obtener opciones traducidas desde Odoo
            #         res_fields = self.env[model_technical_name].fields_get([field_name])
            #         selection_options = res_fields[field_name].get('selection', [])
                    
            #         val_raw = str(value).strip()
            #         val_lower = val_raw.lower()
                    
            #         found_key = False
            #         for key, label in selection_options:
            #             # Comparación flexible: Clave exacta, Clave minúscula o Etiqueta minúscula
            #             if val_raw == str(key) or val_lower == str(key).lower() or val_lower == str(label).lower():
            #                 value = key  # Asignamos la KEY original de la DB (ej: 'Casado')
            #                 found_key = True
            #                 break
                    
            #         if not found_key:
            #             _logger.warning("Irene: No se pudo mapear '%s' en el campo %s", val_raw, field_name)
            #     except Exception as e:
            #         _logger.error("Error en mapeo de selección: %s", str(e))
            elif line.ttype == 'selection':
                try:
                    model_technical_name = line.field_id.model_id.model
                    res_fields = self.env[model_technical_name].fields_get([field_name])
                    selection_options = res_fields[field_name].get('selection', [])
                    
                    val_raw = str(value).strip()
                    val_lower = val_raw.lower()

                    if 'blood_group' in field_name:
                        val_lower = val_lower.replace(' positivo', '+').replace(' negativo', '-')
                        val_lower = val_lower.replace(' más', '+').replace(' menos', '-')
                        val_lower = val_lower.replace(' ', '') # "o +" -> "o+"

                    if 'gender' in field_name or 'sex' in field_name:
                        if val_lower in ['mujer', 'femenina', 'dama', 'female']:
                            val_lower = 'female'
                        elif val_lower in ['hombre', 'masculino', 'caballero', 'male']:
                            val_lower = 'male'
                        print('val_lower', val_lower)

                    found_key = False
                    for key, label in selection_options:
                        # key_str = str(key).lower()
                        # label_str = str(label).lower()

                        if val_lower == str(key).upper() or val_lower == str(label).upper():
                            final_vals[field_name] = key
                            found_key = True
                            break
                    
                    if not found_key:
                        _logger.warning("Irene: No se pudo mapear '%s' en el campo %s", val_raw, field_name)
                        # final_vals[field_name] = value

                except Exception as e:
                    _logger.error("Error en mapeo de selección: %s", str(e))

            # # 3. PROCESAMIENTO MANY2ONE (Búsqueda e Interacción)
            # if line.ttype == 'many2one':
            #     target_model = line.field_id.relation
            #     # Búsqueda por nombre (insensible a mayúsculas/minúsculas)
            #     clean_value = str(value).strip().replace('.', '') # Quita puntos por si la IA pone Dr.
            #     record = self.env[target_model].search([('name', 'ilike', clean_value)], limit=1)
                
            #     if record:
            #         final_vals[field_name] = record.id
            #     else:
            #         # Aplicamos la lógica de interacción definida en la línea
            #         if line.m2o_interaction == 'strict':
            #             raise ValidationError(f"No se encontró un registro coincidente para {line.field_description}: '{value}'")
                    
            #         elif line.m2o_interaction == 'suggest':
            #             # Aquí podrías lanzar un error especial que el JS capture para preguntar
            #             # Por ahora, para no romper el flujo, lanzamos advertencia
            #             raise ValidationError(f"IRENE_CONFIRM_CREATE|{target_model}|{value}")
                    
            #         elif line.m2o_interaction == 'inform':
            #             _logger.info("Many2one no encontrado para %s, se omite.", field_name)
            #             continue # No lo añade a final_vals
            if line.ttype == 'many2one':
                target_model = line.field_id.relation
                
                # Limpieza de títulos y etiquetas de la IA
                noise_words = ['dr  ', 'dra', 'doctor', 'doctora', 'paciente', 'profesional', 'sr', 'sra']
                val_clean = str(value).lower().replace('.', '').strip()
                words = [w for w in val_clean.split() if w not in noise_words]
                search_value = " ".join(words) if words else val_clean

                # Buscamos TODOS los registros que coincidan parcialmente
                records = self.env[target_model].search([('name', 'ilike', search_value)])

                if len(records) == 1:
                    # Único resultado: lo asignamos directamente (ej: "Wilson" -> "Wilson Pedro")
                    final_vals[field_name] = records.id
                    
                elif len(records) > 1:
                    # Múltiples resultados: lanzamos un error estructurado para que el JS pregunte
                    options = ", ".join([f"{r.name}" for r in records[:5]]) # Limitamos a 5 para no saturar
                    raise ValidationError(
                        f"IRENE_MULTIPLE_CHOICE|{field_name}|He encontrado varios registros: {options}. "
                        "¿A cuál de ellos te refieres?"
                    )
                    
                else:
                    # No hay resultados: lógica según configuración
                    if line.m2o_interaction == 'strict':
                        raise ValidationError(f"No pude encontrar a nadie llamado '{value}' en {line.field_description}.")
                    
                    elif line.m2o_interaction == 'suggest':
                        # Lógica para preguntar si desea crearlo
                        raise ValidationError(f"IRENE_CONFIRM_CREATE|{target_model}|{value}")
                        
                    elif line.m2o_interaction == 'inform':
                        _logger.info("Many2one no encontrado para %s, se omite.", field_name)
                        continue
            else:
                # Si no es Many2one, pasamos el valor (ya validado o mapeado)
                final_vals[field_name] = value

        return final_vals

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
    @api.model
    def voice_execute(self, model_name, values):
        """
        Método principal que decide si crear, validar o ejecutar Python.
        """
        print("Ejecutando comando de voz para modelo:", model_name)
        print("Valores recibidos de la IA:", values)
        active_id = values.pop('active_id', False)
        action_type = self.env.context.get('voice_action_type')
        if not action_type:
            return {'status': 'error', 'message': 'No se especificó una acción (create/edit/filter)'}

        config = self.env['voice.command.config'].search([
            ('model_id.model', '=', model_name),
            ('action_type', '=', action_type)
        ], limit=1)
        if not config:
            raise models.ValidationError(f"No hay configuración para {model_name}")

        # --- FASE 1: CONTEXTO PARA EVALUACIÓN ---
        # Definimos qué puede tocar el usuario desde el campo de texto funcional
        eval_context = {
            'env': self.env,
            'values': values, # Los datos que vienen de la IA
            'model': self.env[model_name],
            'result': None,
            'user': self.env.user,
            'requests': wrap_module(requests, ['post', 'get']),
            'logging': _logger,
            'ValidationError': models.ValidationError,
        }

        # --- FASE 2: LÓGICA PRE-EJECUCIÓN (Wizard Funcional) ---
        if config.pre_python_logic:
            # Aquí es donde puedes buscar si el paciente existe o llamar a otra API
            # El código puede modificar 'values' directamente
            print("pre:", config.pre_python_logic)
            safe_eval(config.pre_python_logic, eval_context, mode="exec", nocopy=True)
            print("Valores después de pre_python_logic:", values)
            print("Contexto después de pre_python_logic:", eval_context)
        # Si el código pre-ejecución decide que no se debe crear nada (ej: ya existía), 
        # puede retornar un ID o un mensaje en el contexto.
        if eval_context.get('stop_execution'):
            return eval_context.get('result_data') or True

        # --- FASE 3: PROCESAMIENTO DE CAMPOS (Tu lógica Many2one) ---
        print("Valores antes de preparar final_vals:", values)
        final_vals = self._prepare_final_values(config, values)

        # --- FASE 4: ACCIÓN ---
        if config.action_type == 'create':
            new_record = self.env[model_name].create(final_vals)
            
            # --- FASE 5: LÓGICA POST-EJECUCIÓN ---
            if config.post_python_logic:
                eval_context.update({'record': new_record})
                safe_eval(config.post_python_logic, eval_context, mode="exec", nocopy=True)
        
        if config.action_type == 'edit':
            record = False 
            if active_id:
                record = self.env[model_name].browse(active_id)
            elif values.get('vat'):
                record = self.env[model_name].search([('vat', '=', values['vat'])], limit=1)

            if record and record.exists():
                # Limpiamos valores vacíos para no borrar datos existentes por error
                clean_values = {k: v for k, v in values.items() if v}
                record.write(clean_values)
                print(f"Registro {record.name} actualizado con: {clean_values}")
                return {
                    'status': 'success',
                    'message': f"Registro {record.name} actualizado correctamente.",
                    'id': record.id
                }
            else:
                return {
                    'status': 'error',
                    'message': "No encontré el registro para editar. ¿Deseas crearlo?"
                }
            
            # --- FASE 5: LÓGICA POST-EJECUCIÓN ---

            
            # return new_record.id
        
        return {
            'status': 'created',
            'id': new_record.id,
            'model': model_name,
            'message': f"He creado el registro de {values.get('name', 'el paciente')} exitosamente."
        }

    # DISGREGACIÓN

    def _ai_parse_disaggregation(self, text, config):
        # 1. Preparar las reglas basadas en las líneas del Wizard
        rules_list = []
        for line in config.line_ids:
            rules_list.append({
                'field': line.field_id.name,
                'instruction': line.instruction,
                'type': line.field_id.ttype
            })
        
        rules_string = json.dumps(rules_list, ensure_ascii=False)

        # 2. Llamada al servicio de Groq
        ai_response = self._call_groq_api_service(text, rules_string)
        
        # DEBUG: Mira esto en tu terminal de Odoo
        print("DEBUG IRENE - Respuesta Completa IA:", ai_response)

        if ai_response.get('status') == 'success' or 'data' in ai_response:
            # Tu controlador devuelve la data dentro de 'data'
            extracted_data = ai_response.get('data', {})
            return self._format_values_for_odoo(extracted_data, config)
        else:
            reason = ai_response.get('reasoning') or "Sin detalle del error"
            _logger.error("Error de la IA Irene: %s", reason)
            return {}

    def _call_groq_api_service(self, text, rules):
        icp = self.env['ir.config_parameter'].sudo()
        api_key = icp.get_param('voice_to_text.groq_key')
        
        if not api_key:
            return {"status": "error", "reasoning": "API Key no encontrada en parámetros"}

        url = "https://api.groq.com/openai/v1/chat/completions"
        
        # Usamos tu System Prompt del controlador (adaptado a disgregación)
        system_prompt = f"""
            Eres Irene, IA de procesamiento clínico. Tu objetivo es DISGREGAR el relato en campos técnicos.
            REGLAS:
            1. Usa los campos definidos en la CONFIGURACIÓN.
            2. Devuelve un JSON con: "status", "data", "reasoning".
            3. En "data", coloca {{ "campo_tecnico": "valor" }}.
            
            CONFIGURACIÓN DE CAMPOS:
            {rules}
        """

        payload = {
            "model": "llama-3.1-8b-instant",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f'Analiza este relato y disgrégalo: "{text}"'}
            ],
            "temperature": 0.1,
            "response_format": {"type": "json_object"}
        }

        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=15)
            if response.status_code == 200:
                raw_content = response.json()['choices'][0]['message']['content']
                # Parseamos el string que devuelve Groq a un diccionario de Python
                return json.loads(raw_content)
            else:
                return {"status": "error", "reasoning": f"Código Groq: {response.status_code}"}
        except Exception as e:
            return {"status": "error", "reasoning": str(e)}


    def _format_values_for_odoo(self, data, config):
        final_vals = {}
        for field_name, value in data.items():
            # 1. Buscar metadatos del campo
            field_obj = self.env['ir.model.fields'].search([
                ('model_id', '=', config.model_id.id),
                ('name', '=', field_name)
            ], limit=1)

            if not field_obj or value is None:
                continue

            ttype = field_obj.ttype
            val_str = str(value).strip()

            # --- LÓGICA POR TIPO DE CAMPO ---

            # BOOLEANOS: "Sí", "No", "True", "False"
            if ttype == 'boolean':
                final_vals[field_name] = val_str.lower() in ['si', 'sí', 'yes', 'true', '1', 'activo', 'verdadero', 'confirmado']

            # SELECCIÓN: Mapear etiqueta -> valor técnico
            elif ttype == 'selection':
                # 1. Obtener las opciones (Key, Label) usando el método estándar de Odoo
                # Esto devuelve las etiquetas ya traducidas según el idioma del usuario (self.env.lang)
                selection_options = self.env[config.model_name].fields_get([field_name])[field_name].get('selection', [])
                
                val_clean = val_str.lower().strip()
                
                # Función de normalización para ignorar acentos
                def _normalize(text):
                    import unicodedata
                    if not text: return ""
                    return "".join(c for c in unicodedata.normalize('NFD', str(text))
                                if unicodedata.category(c) != 'Mn').lower()

                val_norm = _normalize(val_clean)
                found_key = False
                
                for key, label in selection_options:
                    # Comparamos contra la CLAVE técnica y contra la ETIQUETA traducida
                    if val_clean in [str(key).lower(), str(label).lower()] or \
                    val_norm in [_normalize(key), _normalize(label)]:
                        final_vals[field_name] = key
                        found_key = True
                        break
                
                if not found_key:
                    _logger.warning("Irene: El valor '%s' no coincide con ninguna opción de %s", val_str, field_name)
            
            # MANY2ONE: Buscar el registro por nombre
            elif ttype == 'many2one':
                rel_model = self.env[field_obj.relation]
                res = rel_model.search([('name', 'ilike', val_str)], limit=1)
                if res:
                    final_vals[field_name] = res.id

            # MANY2MANY / ONE2MANY: (Ya lo teníamos, pero mejorado)
            elif ttype in ['many2many', 'one2many']:
                rel_model = self.env[field_obj.relation]
                names = value if isinstance(value, list) else [val_str]
                tag_ids = []
                for name in names:
                    tag = rel_model.search([('name', 'ilike', name)], limit=1)
                    if not tag:
                        tag = rel_model.create({'name': name})
                    tag_ids.append(tag.id)
                final_vals[field_name] = [(6, 0, tag_ids)]

            # NÚMEROS (Integer / Float)
            elif ttype in ['integer', 'float']:
                # Extraer solo números y puntos usando Regex
                number_match = re.search(r"[-+]?\d*\.\d+|\d+", val_str)
                if number_match:
                    num_val = float(number_match.group())
                    final_vals[field_name] = int(num_val) if ttype == 'integer' else num_val

            # FECHAS
            elif ttype == 'date':
                try:
                    # Odoo espera YYYY-MM-DD. Intentamos limpiar lo que mande la IA
                    final_vals[field_name] = fields.Date.to_date(val_str)
                except:
                    pass # Si falla el formato, ignoramos para no romper el write

            # TEXTO / CHAR: Directo
            else:
                final_vals[field_name] = val_str

        return final_vals


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

    help_instructions = fields.Text(
        string="Instrucciones del Sistema",
        help="Instrucción específica que se le pasará a la IA sobre este campo."
    )

    question_if_missing = fields.Char(
        string="Pregunta si falta",
        help="Frase que dirá Irene si el campo es obligatorio y no se detectó en el audio."
    )

    is_required = fields.Boolean(string="Obligatorio")

    has_range = fields.Boolean(string="Tiene Rango")
    min_value = fields.Float(string="Valor Mínimo")
    max_value = fields.Float(string="Valor Máximo")

    m2o_interaction = fields.Selection([
        ('strict', 'Estricto (Debe existir)'),
        ('suggest', 'Sugerir creación si no existe'),
        ('inform', 'Informar que no existe y omitir')
    ], string="Comportamiento Many2one", default='strict')

    # Para Selection (Diccionario de mapeo)
    selection_mapping = fields.Text(
        string="Mapeo de Selección (JSON)",
        help='Ejemplo: {"grave": "serious", "urgente": "high"}'
    )

    def action_generate_selection_mapping(self):
        """
        Lee la definición del campo Selection en Odoo y genera un 
        template JSON en selection_mapping.
        """
        self.ensure_one()
        if self.ttype != 'selection':
            return
            
        # Obtenemos el modelo y el campo real de Odoo
        obj = self.env[self.parent_model_id.model]
        field = obj._fields.get(self.name)
        
        if field and hasattr(field, 'selection'):
            selection_values = []
            
            # El atributo selection puede ser una lista o una función
            if callable(field.selection):
                selection_values = field.selection(obj)
            else:
                selection_values = field.selection
            
            # Creamos un diccionario: {"Etiqueta Humana": "valor_tecnico"}
            # Lo ponemos en minúsculas para facilitar el match de la IA
            mapping = {str(label).lower(): str(key) for key, label in selection_values}
            
            # Lo guardamos formateado como JSON nítido
            self.selection_mapping = json.dumps(mapping, indent=4, ensure_ascii=False)

    @api.constrains('selection_mapping')
    def _check_selection_mapping_json(self):
        for record in list(self):
            if record.selection_mapping:
                try:
                    # Intentamos cargar el texto como JSON
                    data = json.loads(record.selection_mapping)
                    
                    # Opcional: Validar que sea un diccionario y no una lista
                    if not isinstance(data, dict):
                        raise ValidationError(
                            "El mapeo de selección debe ser un objeto JSON válido. "
                            "Ejemplo: {'termino_ia': 'valor_odoo'}"
                        )
                except (ValueError, TypeError):
                    raise ValidationError(
                        f"Error de sintaxis en el campo 'Mapeo de Selección' del campo {record.field_description}. "
                        "Asegúrate de usar comillas dobles y un formato JSON válido."
                    )