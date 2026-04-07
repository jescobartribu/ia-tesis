/** @odoo-module **/
import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Dialog } from "@web/core/dialog/dialog";
import { loadJS } from "@web/core/assets";

// Definimos la clase del Wizard/Dialog que verá el usuario
class VoiceAssistantDialog extends Component {}
VoiceAssistantDialog.template = "voice_to_text.AssistantDialog";
VoiceAssistantDialog.components = { Dialog };
VoiceAssistantDialog.props = ["*"];

export class VoiceSystray extends Component {

    setup() {
        this.user = useService("user");
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.productos = [];
        this.rpc = useService("rpc");
        this.silenceTimer = null;
        this.voiceState = useState({
            isListening: false, // Micrófono encendido
            isAwake: false,     // ¿Ya dijo "Irene"?
            isPaused: false,
            transcript: "",
            accumulatedText: ""
        });
        this.voiceConfigs = [];
        this.isSentinelActive = false; 
        this.isAwake = false;
        this.voiceState.isProcessing = true;

        onWillStart(async () => {
            // 1. Cargamos las cabeceras de configuración
            const configs = await this.orm.searchRead(
                "voice.command.config", 
                [], 
                ["name", "model_name", "trigger_words", "action_type"]
            );
            
            // 2. Traemos TODAS las líneas de una sola vez (más rápido para el servidor)
            // Extraemos todos los IDs de las configuraciones para filtrar
            const configIds = configs.map(c => c.id);
            
            const allFields = await this.orm.searchRead(
                "voice.command.config.line",
                [["parent_id", "in", configIds]],
                ["name", "name_ia", "ttype", "selection_mapping", "help_instructions", "parent_id"] 
            );

            // 3. Repartimos los campos a sus respectivas configuraciones
            for (let config of configs) {
                config.fields = allFields.filter(f => {
                    // Manejamos que parent_id puede venir como [id, "name"]
                    const pId = Array.isArray(f.parent_id) ? f.parent_id[0] : f.parent_id;
                    return pId === config.id;
                });
            }

            this.voiceConfigs = configs;
            console.log('Irene: Configuraciones cargadas con metadatos completos', this.voiceConfigs);
        });

        this.recognition = new (window.SpeechRecognition || window.webkitSpeechRecognition)();
        this.recognition.continuous = true; // Fundamental para que no se apague
        this.recognition.interimResults = true; // Para capturar la palabra clave rápido
        // Precarga de voces para evitar que la primera vez no hable
        window.speechSynthesis.getVoices();
        if (window.speechSynthesis.onvoiceschanged !== undefined) {
            window.speechSynthesis.onvoiceschanged = () => window.speechSynthesis.getVoices();
        }
        let voces = [];
        function cargarVoces() {
            voces = speechSynthesis.getVoices();
            // Filtrar solo las voces en español
            let vocesEspañol = voces.filter(voz => voz.lang.includes('es'));
            console.log(vocesEspañol);  
            }
        speechSynthesis.onvoiceschanged = cargarVoces;


        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        this.dialogService = useService("dialog");
        console.log("VoiceSystray montado, buscando SpeechRecognition:", SpeechRecognition);
        
        if (SpeechRecognition) {
            this.recognition = new SpeechRecognition();
            this.recognition.lang = 'es-ES';
            this.recognition.continuous = true;
            this.recognition.interimResults = true;
            

            // --- EL MOTOR SIEMPRE LISTO ---
            this.recognition.onresult = (event) => {
                const text = event.results[event.results.length - 1][0].transcript.toLowerCase().trim();
                const result = event.results[event.results.length - 1];

                if (text.includes("detente") || text.includes("pausa")) {
                    this.voiceState.isPaused = true;
                    clearTimeout(this.silenceTimer); // No procesar si pausamos
                    this._speak("Pausado.");
                    return;
                }

                if (this.voiceState.isPaused) {
                    if (text.includes("continúa") || text.includes("sigue")) {
                        this.voiceState.isPaused = false;
                        this._speak("Reanudado.");
                    }
                    return;
                }

                // --- LÓGICA DE ACUMULACIÓN Y DISPARO ---
                if (this.isAwake) {
                    // Mostramos el texto intermedio para que el usuario vea que Irene escucha
                    this.voiceState.transcript = this.voiceState.accumulatedText + " " + text;

                    if (result.isFinal) {
                        this.voiceState.accumulatedText += " " + text;
                        
                        // CADA VEZ QUE HAY UNA FRASE FINAL, REINICIAMOS EL CRONÓMETRO
                        clearTimeout(this.silenceTimer);
                        
                        this.silenceTimer = setTimeout(() => {
                            console.log("Silencio detectado. Enviando a la IA...");
                            this._finalizeCommand();
                        }, 6000); // segundos de silencio para procesar
                    }
                } else {
                    // --- MODO CENTINELA ---
                    // Si no está despierta, solo buscamos la palabra "irene"
                    if (text.includes("irene")) {
                        this.voiceState.accumulatedText = ""; 
                        this.voiceState.transcript = "";
                        this._wakeUpIrene();
                        // Limpiamos el texto para que no se procese la palabra "irene" como parte del comando
                    }
                }
            };

            // --- EL REANIMADOR (Crucial para que no muera) ---
            this.recognition.onend = () => {
                // console.log("Micro apagado. ¿Reactivar?:", this.isSentinelActive);
                if (this.isSentinelActive) {
                    try {
                        this.recognition.start();
                    } catch (e) {
                        // Ya estaba encendido, ignoramos
                    }
                }
            };
        }
    }

        // onWillStart(async () => {
        //     this.voiceConfigs = await this.orm.searchRead(
        //         "voice.command.config", 
        //         [], 
        //         ["name", "model_name", "trigger_words", "action_type"]
        //     );
        //     for (let config of this.voiceConfigs) {
        //         config.fields = await this.orm.searchRead(
        //             "voice.command.config.line",
        //             [["parent_id", "=", config.id]],
        //             ["name", "name_ia"]
        //         );
        //     }
        //     console.log('Configuraciones cargadas:', this.voiceConfigs);
            
        //     this.productos = await this.orm.searchRead("product.product", [], ["name"]);
        //         console.log('PRODUCTOS DENTRO DEL HOOK:', this.productos);
        //     // const productNames = this.productos.map(p => p.name).join(' | ');
    
        //     // const grammar = `#JSGF V1.0; grammar products; public <product> = ${productNames};`;
        //     // console.log('Grammar:', grammar);
        //     // this.medicalGrammar = grammar;

        //     // const options = {
        //     //     keys: ['name'],
        //     //     threshold: 0.3, // Ajusta este valor: 0.0 es idéntico, 1.0 es cualquier cosa
        //     //     includeScore: true
        //     // };
        //     // Usamos window.Fuse porque lo cargamos como librería externa en el manifest
        //     // this.fuse = new window.Fuse(this.productos, options);
        //     // console.log("sobrevivio fuse")
        // });
        // this.dialogService = useService("dialog");
        // this.voiceState = useState({ isListening: false, transcript: "" });
        
        // const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        // if (SpeechRecognition) {
        //     this.recognition = new SpeechRecognition();
        //     this.recognition.lang = 'es-ES';
        //     this.recognition.continuous = true;
        //     // this.recognition.continuous = true;
        //     this.recognition.interimResults = true; // Fundamental para que veas el texto mientras hablas

        //     this.recognition.onresult = async (event) => {
        //         const text = event.results[event.results.length - 1][0].transcript.toLowerCase().trim();

        //         if (text.includes("detente") || text.includes("para") || text.includes("stop")) {
        //             this.voiceState.isPaused = true;
        //             this._speak("Entendido, me quedo en espera. Di continúa cuando me necesites.");
        //             this.voiceState.transcript = "En pausa... (Di 'continúa')";
        //             return; // Detenemos cualquier procesamiento posterior
        //         }

        //         // 2. Lógica de Reactivación
        //         if (this.voiceState.isPaused) {
        //             if (text.includes("continúa") || text.includes("sigue") || text.includes("reanudar")) {
        //                 this.voiceState.isPaused = false;
        //                 this._speak("Estoy escuchando de nuevo. ¿En qué te ayudo?");
        //                 this.voiceState.transcript = "Escuchando...";
        //             }
        //             return; // Mientras esté pausado, no procesamos nada más
        //         }
        //         else {
        //             this._speak("Procesando....");
        //         }
        //         clearTimeout(this.silenceTimer);
        //         let interim = "";
        //         let textAccumulated = "";
        //         for (let i = event.resultIndex; i < event.results.length; ++i) {
        //             interim += event.results[i][0].transcript;
        //             if (event.results[i].isFinal) {
        //                 // FUSE.JS PARA CORREGIR
        //                 if (interim.includes("filtrar") || interim.includes("crear")) {
        //                     console.log("Comando detectado, saltando Fuse.js");
        //                     textAccumulated = interim; // Mantenemos el comando limpio
        //                 } else {
        //                     console.log("antes fuzzy", interim)
        //                     textAccumulated += this._fuzzyCorrect(interim) + " ";
        //                     console.log("despues fuzzy", textAccumulated)
        //                 }
        //             } else {
        //                 textAccumulated += interim;
        //             }
        //         }
        //         this.voiceState.transcript = textAccumulated;
        //         this.silenceTimer = setTimeout(() => {
        //         if (this.voiceState.transcript.trim() !== "") {
        //             console.log("3 segundos de silencio. Procesando:", this.voiceState.transcript);
        //             // this._onVoiceComplete(this.voiceState.transcript);
        //         }
        //     }, 100);
        //     }
        //     this.recognition.onend = () => { 
        //     // Si el reconocimiento se detiene por error del navegador, lo reiniciamos si seguíamos en modo 'Listening'
        //         if (this.voiceState.isListening) {
        //             this.recognition.start();
        //         }
        //     };
        // }
    // }

    // async _finalizeCommand() {
    //     clearTimeout(this.silenceTimer); // Por seguridad
    //     const finalSentence = this.voiceState.accumulatedText.trim();

    //     if (finalSentence === "irene" || !finalSentence || finalSentence === "...") {
    //         console.log("Ignorando comando: Solo se detectó el nombre de activación.");
    //         return; 
    //     }
    //     this.voiceState.isProcessing = true; // Activa la animación
    //     this.voiceState.transcript = "Procesando...";
        
        

    //     this._speak("Procesando comando..."); // Feedback visual/auditivo

    //     if (this.voiceState.pendingAction) {
    //         console.log("Resolviendo duda con Irene:", finalSentence);
    //         const action = this.voiceState.pendingAction;

    //         if (action.type === 'selection_m2o') {
    //             // 1. Inyectamos la respuesta en la data de la CITA original
    //             action.aiData.data[action.field] = finalSentence;
                
    //             // 2. Guardamos la referencia y LIMPIAMOS TODO antes de reintentar
    //             const originalAppointmentData = action.aiData;
    //             this.voiceState.pendingAction = null; 
    //             this.voiceState.accumulatedText = ""; 

    //             this._speak(`Entendido, asignando a ${finalSentence}...`);

    //             // 3. REINTENTAMOS el proceso de Odoo (sin pasar por Groq/IA)
    //             try {
    //                 await this._processCommands(originalAppointmentData);
    //             } catch (error) {
    //                 console.error("Error al reintentar cita:", error);
    //             }
                
    //             // 4. IMPORTANTE: return para que NO se ejecute el código de abajo (la IA)
    //             return; 
    //         }
    //     }

    //     try {
    //         let aiData = await this._apiIA(finalSentence);
    //         if (aiData && aiData.status === "success") {
    //             await this._processCommands(aiData);
    //             this.voiceState.accumulatedText = ""; // Limpiar tras éxito
    //             this.voiceState.transcript = "Comando ejecutado.";
    //             this.voiceState.isProcessing = false;
    //         }
    //     } catch (error) {
    //         // const msg = error.data?.message || "";
    //         // if (msg.includes("IRENE_MULTIPLE_CHOICE") || msg.includes("IRENE_CONFIRM_CREATE")) {
    //         //     this.voiceState.isProcessing = false;
    //         //     return;
    //         // }
    //         // else {
    //             console.error("Error procesando con IA:", error);
    //             this._speak("Lo siento, ocurrió un error al procesar tu comando.");
    //         // }
    //     }
        
    //     // Auto-cerrar el wizard tras procesar
    //     setTimeout(() => {
    //         if (this.isAwake && !this.voiceState.pendingAction) {
    //             this.isAwake = false;
    //             if (this.closeWizard) this.closeWizard();
    //             if (this.isSentinelActive) {
    //                 try { this.recognition.start(); } catch(e) {}
    //             }
    //         }
    //     }, 2000);
    // }
    // async _finalizeCommand() {
    //     clearTimeout(this.silenceTimer);
    //     // Usamos el texto acumulado que Irene escuchó mientras esperaba
    //     const finalSentence = this.voiceState.accumulatedText.trim().toLowerCase();

    //     if (!finalSentence || finalSentence === "irene") return;

    //     console.log("Analizando comando final:", finalSentence);

    //     if (this.voiceState.pendingAction) {
    //         const action = this.voiceState.pendingAction;
    //         console.log("Duda detectada. Aplicando respuesta a:", action.field);

    //        if (action.type === 'selection_m2o') {
    //             // Clonación profunda para evitar referencias
    //             const retryData = JSON.parse(JSON.stringify(action.aiData));
    //             retryData.data[action.field] = finalSentence;
                
    //             this.voiceState.pendingAction = null;
    //             this.voiceState.accumulatedText = ""; 
                
    //             this._speak(`Entendido, seleccionando ${finalSentence}.`);
    //             await this._processCommands(retryData);
    //             return; 
    //         }
    //     }

    //     // --- FLUJO NORMAL (Solo si no había nada pendiente) ---
    //     this.voiceState.isProcessing = true;
    //     this.voiceState.transcript = "Procesando...";
    //     this._speak("Procesando comando...");

    //     try {
    //         // Solo llamamos a la IA si no estamos en medio de una resolución de duda
    //         let aiData = await this._apiIA(finalSentence);
    //         if (aiData && aiData.status === "success") {
    //             await this._processCommands(aiData);
    //             this.voiceState.accumulatedText = ""; 
    //         }
    //     } catch (error) {
    //         console.error("Error en IA:", error);
    //     }
    // }
    async _finalizeCommand() {
        clearTimeout(this.silenceTimer);
        
        const finalSentence = this.voiceState.accumulatedText.trim().toLowerCase();

        // Si no hay texto o solo dijo su nombre, reseteamos y volvemos a modo espera
        if (!finalSentence || finalSentence === "irene") {
            this._resetToSentinel();
            return;
        }

        console.log("Analizando comando final:", finalSentence);

        // --- CASO 1: RESOLUCIÓN DE DUDAS (Pending Action) ---
        if (this.voiceState.pendingAction) {
            const action = this.voiceState.pendingAction;
            console.log("Duda detectada. Aplicando respuesta a:", action.field);

            if (action.type === 'selection_m2o') {
                const retryData = JSON.parse(JSON.stringify(action.aiData));
                retryData.data[action.field] = finalSentence;
                
                this.voiceState.pendingAction = null;
                this._speak(`Entendido, seleccionando ${finalSentence}.`);
                
                await this._processCommands(retryData);
                this._resetToSentinel(); // IMPORTANTE: Volver a esperar a "Irene"
                return; 
            }
        }

        // --- CASO 2: FLUJO NORMAL (Llamada a la IA) ---
        this.voiceState.isProcessing = true;
        this.voiceState.transcript = "Procesando...";
        // this._speak("Procesando comando..."); // Opcional, puede ser molesto si es muy seguido

        try {
            let aiData = await this._apiIA(finalSentence);
            
            if (aiData && aiData.status === "success") {
                await this._processCommands(aiData);
            } else if (aiData && aiData.status === "error") {
                this._speak("Lo siento, hubo un error al procesar la solicitud.");
            }
        } catch (error) {
            console.error("Error en IA:", error);
            this._speak("Ocurrió un error de conexión.");
        } finally {
            // --- SIEMPRE REGRESAR AL MODO CENTINELA AL FINALIZAR ---
            this._resetToSentinel();
        }
    }

    /**
     * Función auxiliar para limpiar el estado y volver al modo centinela
     */
    _resetToSentinel() {
        this.isAwake = false;
        this.voiceState.isAwake = false;
        this.voiceState.isProcessing = false;
        this.voiceState.accumulatedText = ""; 
        this.voiceState.transcript = "";
        console.log("Irene: Regresando a modo centinela...");
    }
    async _apiIA(text) {
        // Mantienes tu lógica de reglas dinámicas porque OWL conoce el estado de la UI
        console.log("Texto a enviar a la IA:", text);
        const cleanedTranscript = text.replace(/(\d)\s+(\d)/g, '$1$2');
        console.log("Texto enviado a la IA corregido:", cleanedTranscript);
        // const reglasDinamicas = this.voiceConfigs.map(c => {
        //     const campos = c.fields.map(f => `- Campo técnico: "${f.name}" (el usuario lo llamará: "${f.name_ia || f.name}")`).join("\n");
        //     return `COMANDO: ${c.name}\n- Usar modelo: "${c.model_name}"\n- Intención: "${c.action_type}"\n- Campos:\n${campos}`;
        // }).join("\n\n");
        console.log("Revisando estructura de voiceConfigs:", this.voiceConfigs);
        const reglasDinamicas = this.voiceConfigs.map(c => {
            const campos = c.fields.map(f => {
                let info = `- Campo: "${f.name}" (Usuario dice: "${f.name_ia || f.name}")`;
                console.log(`Procesando campo: ${f.name}, Tipo: ${f.ttype}, Tiene Mapping: ${!!f.selection_mapping}`);
                
                // Si tiene mapeo de selección, se lo inyectamos a la IA
                // if (f.ttype === 'selection' && f.selection_mapping) {
                //     const mapStr = JSON.stringify(f.selection_mapping);
                //     info += `\n  ⚠️ REGLA DE SELECCIÓN: Si el usuario menciona algo similar a las llaves de este diccionario: ${mapStr}, debes devolver el VALOR asociado. El output debe ser exclusivamente la llave técnica en inglés. No uses lenguaje natural.`;
                // }
                if (f.ttype === 'selection' && f.selection_mapping) {
                    let mappingValido = null;

                    // Intentamos convertir el texto de Odoo en un objeto real de JS
                    try {
                        mappingValido = typeof f.selection_mapping === 'string' 
                            ? JSON.parse(f.selection_mapping) 
                            : f.selection_mapping;
                    } catch (e) {
                        console.error("Error al parsear selection_mapping para el campo:", f.name);
                    }

                    if (mappingValido) {
                        const transformaciones = Object.entries(mappingValido)
                            .map(([key, value]) => `    - "${key}" → "${value}"`)
                            .join("\n");

                        info += `\n  ⚠️ REGLA DE TRADUCCIÓN OBLIGATORIA:
                Sustituye lo que diga el usuario por el valor técnico exacto:
                ${transformaciones}
                * Nota: El resultado en el JSON debe ser solo el valor de la derecha.`;
                    }
                }
                if (f.ttype === 'text' || f.ttype === 'html') {
                    info += `\n  ⚠️ REGLA DE CAPTURA: Este campo es de texto largo. NO intentes desglosar su contenido en otros campos. Vuelca toda la narrativa aquí de forma íntegra.`;
                }
                // if (f.ttype === 'text' || f.ttype === 'html') {
                //     info += `\n  🚨 REGLA DE ORO: NO RESUMAS. Copia LITERALMENTE cada palabra que el usuario diga sobre el motivo o descripción. Si el usuario habla por 1 minuto, pon las 100 palabras aquí. Es un error crítico omitir detalles médicos.`;
                // }
                // Si tiene instrucciones extra (help_instructions)
                if (f.help_instructions) {
                    info += `\n  📝 NOTA: ${f.help_instructions}`;
                }
                
                return info;
            }).join("\n");

            return `COMANDO: ${c.name}\n- Modelo: "${c.model_name}"\n- Intención: "${c.action_type}"\n- Campos y Reglas:\n${campos}`;
        }).join("\n\n");

        try {
            // Llamada al servidor Odoo
            console.log("Enviando a Odoo para procesamiento con IA. Texto limpio:", cleanedTranscript);
            console.log("Reglas dinámicas enviadas a Odoo:", reglasDinamicas);
            const aiData = await this.rpc('/groq/process_command', {
                text: cleanedTranscript,
                rules: reglasDinamicas
            });

            console.log("Respuesta de Irene:", aiData);
            return aiData;

        } catch (error) {
            console.error("Fallo la comunicación con el servidor Odoo:", error);
            return { status: "error", reasoning: "No se pudo contactar con el servidor" };
        }
    }

    _fuzzyCorrect(text) {
        if (!this.fuse) return text;
        
        const words = text.split(" ");
        const corrected = words.map(word => {
            if (word.length < 3) return word; // Ignorar palabras cortas

            const results = this.fuse.search(word);
            // Si hay un resultado con un score bajo (buena coincidencia)
            if (results.length > 0 && results[0].score < 0.4) {
                return results[0].item.name;
            }
            return word;
        });
        return corrected.join(" ");
    }
    
    async _processCommands(aiData) {
        // aiData contiene: { model: 'hms.patient', data: { name: 'Juan' }, intent: 'create' }
        const transcript = aiData.answer
        const audioBase64 = await this.rpc("/fenix/get_audio", { text: transcript });
        const currentController = this.actionService.currentController;
        let activeId = null;
        if (currentController && currentController.props.resModel === aiData.model) {
            activeId = currentController.props.resId || null;
        }
        console.log("ID activo detectado:", activeId, "en modelo:", currentController ? currentController.props.resModel : "N/A");
        try {
            if (aiData.intent === 'create' || aiData.intent === 'edit') {
                const result = await this.rpc("/web/dataset/call_kw/voice.command.config/voice_execute", {
                    model: 'voice.command.config',
                    method: 'voice_execute',
                    args: [aiData.model, { ...aiData.data, active_id: activeId }],
                    kwargs: {
                        context: { ...(this.user?.context || {}), voice_action_type: aiData.intent }
                    },
                });

                console.log(`Resultado de ${aiData.intent}:`, result);

                if (result && (result.id || result.status === 'success')) {
                    // Feedback de voz (Irene habla)
                    const textToSpeak = result.message || "Proceso completado";
                    const audioResult = await this.rpc("/fenix/get_audio", { text: textToSpeak });
                    
                    if (audioResult && !audioResult.error) {
                        const audio = new Audio("data:audio/mp3;base64," + audioResult);
                        audio.play();
                    }

                    // Si fue una edición y ya estamos en el formulario, refrescamos la vista
                    if (aiData.intent === 'edit' && activeId && currentController) {
                        await this.actionService.restore(currentController.jsId);
                    } 
                    // Si fue creación o edición de un registro que no teníamos abierto, navegamos a él
                    if (result && result.status === 'error') {
                        this._speak(result.message); // Irene dirá: "No encontré al profesional Dr Wilson"
                        return;
                    }
                    else if (result.id) {
                        await this.actionService.doAction({
                            type: "ir.actions.act_window",
                            res_model: result.model || aiData.model,
                            res_id: result.id,
                            views: [[false, "form"]],
                            target: "current",
                        });
                    }
                }
            }
            else if (aiData.intent === "filter") {
                // FILTRO DINÁMICO
                const domain = [];
                for (let campo in aiData.data) {
                    domain.push([campo, "ilike", aiData.data[campo]]);
                }

                await this.actionService.doAction({
                    type: "ir.actions.act_window",
                    name: `Búsqueda por Voz: ${aiData.model}`,
                    res_model: aiData.model,
                    views: [[false, "list"], [false, "form"]],
                    domain: domain,
                    target: "current",
                });
                this.voiceState.transcript = `🔍 Filtrando ${aiData.model}...`;
            }
            else if (aiData.intent === "search") {
                console.log("Ejecutando búsqueda con dominio:", aiData.data);
                const domain = [];
                for (let field in aiData.data) {
                    domain.push([field, "ilike", aiData.data[field]]);
                }

                // Primero buscamos en el servidor si existe el registro
                const records = await this.orm.searchRead(aiData.model, domain, ["id"], { limit: 2 });

                if (records.length === 1) {
                    // Si solo hay uno, vamos directo al FORMULARIO
                    await this.actionService.doAction({
                        type: "ir.actions.act_window",
                        res_model: aiData.model,
                        res_id: records[0].id,
                        views: [[false, "form"]],
                        target: "current",
                    });
                    this._speak("He encontrado al paciente. Aquí tienes su ficha.");
                } else if (records.length > 1) {
                    // Si hay varios, mostramos la LISTA (comportamiento de filtro)
                    await this.actionService.doAction({
                        type: "ir.actions.act_window",
                        name: `Coincidencias de búsqueda`,
                        res_model: aiData.model,
                        views: [[false, "list"], [false, "form"]],
                        domain: domain,
                        target: "current",
                    });
                    this._speak("He encontrado varias coincidencias. Selecciona la correcta.");
                } else {
                    this._speak("Lo siento, no encontré ningún registro con esos datos.");
                }
            }
        } catch (error) {
            console.error("Error en el ORM:", error);
            const msg = error.data ? error.data.message : "Error desconocido";
            if (msg.includes("IRENE_MULTIPLE_CHOICE")) {
                const [_, field, text] = msg.split("|");
                // Extraer nombres: "He encontrado varios registros: A, B, C" -> ["A", "B", "C"]
                const matches = text.split(":")[1].split(",").map(n => n.trim().replace("?", ""));

                if (matches.length > 5) {
                    this._speak("He encontrado demasiadas coincidencias. Por favor, sé más específico con el nombre.");
                } else {
                    // this.voiceState.pendingAction = {
                    //     type: 'selection',
                    //     field: field,
                    //     options: matches,
                    //     text: text,
                    //     aiData: aiData // Guardamos el comando original para reintentar
                    // };
                    // this.voiceState.transcript = "Esperando que elijas una opción...";
        
                    // // --- ADICIÓN CRÍTICA ---
                    // this.voiceState.accumulatedText = ""; 
                    // this.voiceState.transcript = "";
                    // // ------------------------

                    this._speak(text);
                }
                return; // Detenemos la ejecución
            }

            // 2. Manejo de Confirmación de Creación
            if (msg.includes("IRENE_CONFIRM_CREATE")) {
                const [_, model, name] = msg.split("|");
                this.voiceState.pendingAction = {
                    type: 'create_m2o',
                    model: model, // Modelo a crear (ej: res.partner)
                    name: name,   // Nombre a ponerle
                    aiData: aiData // Acción original (ej: crear cita)
                };
                this._speak(`No encontré a ${name}. ¿Quieres que lo cree en el sistema?`);
                return;
            }

            // Error genérico de Odoo
            this._speak("Lo siento, ocurrió un error en el servidor: " + msg);
        }
    }        

    async _speak(text) {
        try {
            if (this.currentAudio) {
                this.currentAudio.pause();
            }
            const audioBase64 = await this.rpc('/fenix/get_audio', {
                text: text,
            });

            if (audioBase64.error) {
                console.error("Error desde el servidor:", audioBase64.error);
                return;
            }
            this.currentAudio = new Audio(`data:audio/mpeg;base64,${audioBase64}`);
            this.currentAudio.play();
            return this.currentAudio;
        } catch (error) {
            console.error("Error en la llamada RPC:", error);
        }
    }

    async _initFuse() {
        if (this.fuse) return; // Si ya está listo, no hacer nada

        // 1. Cargamos el archivo físicamente
        await loadJS("/voice_to_text/static/lib/fuse.basic.min.js");
        
        // 2. Ahora que ya cargó, window.Fuse ya existe
        const options = {
            keys: ['name'],
            threshold: 0.1,
            includeScore: true
        };
        this.fuse = new window.Fuse(this.productos, options);
        console.log("Fuse inicializado correctamente");
    }

    _wakeUpIrene() {
        clearTimeout(this.silenceTimer);
        this.isAwake = true;
        this.voiceState.accumulatedText = ""; // Empezamos dictado limpio
        this.voiceState.transcript = "...";

        this._speak("¿Dime, en qué puedo ayudarte?");

        this.closeWizard = this.dialogService.add(VoiceAssistantDialog, {
            title: "Irene AI",
            transcript: this.voiceState,
            onClose: () => {
                this.isAwake = false;
                this.voiceState.accumulatedText = "";
            }, 
        });
    }
    _onClick() {
        if (!this.recognition) return;

        if (this.isSentinelActive) {
            // Apagar todo
            this.isSentinelActive = false;
            this.isAwake = false;
            this.voiceState.isListening = false;
            this.recognition.stop();
            console.log("Irene desactivada.");
        } else {
            // Encender modo escucha
            this.isSentinelActive = true;
            this.voiceState.isListening = true;
            this.recognition.start();
            console.log("Irene en modo centinela (esperando 'Irene')...");
        }
    }

    _activateWizard() {
        // 1. Sonido de activación o saludo
        this._speak("Dime, te escucho.");

        // 2. Abrir el diálogo visual
        this.closeWizard = this.dialogService.add(VoiceAssistantDialog, {
            title: "Irene AI Activa",
            transcript: this.voiceState,
            close: () => {
                this.voiceState.isAwake = false; // Vuelve a modo centinela al cerrar
                this.closeWizard();
            },
        });
    }
}

VoiceSystray.template = "voice_to_text.VoiceSystray";
registry.category("systray").add("voice_to_text.VoiceAssistant", { Component: VoiceSystray });
VoiceSystray.props = {
    "*": true, 
};