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
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.productos = [];
        this.rpc = useService("rpc");
        this.silenceTimer = null;
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

        // Necesario esperar a que carguen
        speechSynthesis.onvoiceschanged = cargarVoces;

        onWillStart(async () => {
            this.voiceConfigs = await this.orm.searchRead(
                "voice.command.config", 
                [], 
                ["name", "model_name", "trigger_words", "action_type"]
            );
            for (let config of this.voiceConfigs) {
                config.fields = await this.orm.searchRead(
                    "voice.command.config.line",
                    [["parent_id", "=", config.id]],
                    ["name", "name_ia"]
                );
            }
            console.log('Configuraciones cargadas:', this.voiceConfigs);
            
            this.productos = await this.orm.searchRead("product.product", [], ["name"]);
                console.log('PRODUCTOS DENTRO DEL HOOK:', this.productos);
            // const productNames = this.productos.map(p => p.name).join(' | ');
    
            // const grammar = `#JSGF V1.0; grammar products; public <product> = ${productNames};`;
            // console.log('Grammar:', grammar);
            // this.medicalGrammar = grammar;

            // const options = {
            //     keys: ['name'],
            //     threshold: 0.3, // Ajusta este valor: 0.0 es idéntico, 1.0 es cualquier cosa
            //     includeScore: true
            // };
            // Usamos window.Fuse porque lo cargamos como librería externa en el manifest
            // this.fuse = new window.Fuse(this.productos, options);
            // console.log("sobrevivio fuse")
        });
        this.dialogService = useService("dialog");
        this.voiceState = useState({ isListening: false, transcript: "" });
        
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        if (SpeechRecognition) {
            this.recognition = new SpeechRecognition();
            this.recognition.lang = 'es-ES';
            this.recognition.continuous = true;
            // this.recognition.continuous = true;
            this.recognition.interimResults = true; // Fundamental para que veas el texto mientras hablas

            this.recognition.onresult = async (event) => {
                clearTimeout(this.silenceTimer);
                let interim = "";
                let textAccumulated = "";
                for (let i = event.resultIndex; i < event.results.length; ++i) {
                    interim += event.results[i][0].transcript;
                    if (event.results[i].isFinal) {
                        // FUSE.JS PARA CORREGIR
                        if (interim.includes("filtrar") || interim.includes("crear")) {
                            console.log("Comando detectado, saltando Fuse.js");
                            textAccumulated = interim; // Mantenemos el comando limpio
                        } else {
                            console.log("antes fuzzy", interim)
                            textAccumulated += this._fuzzyCorrect(interim) + " ";
                            console.log("despues fuzzy", textAccumulated)
                        }
                    } else {
                        textAccumulated += interim;
                    }
                }
                this.voiceState.transcript = textAccumulated;
                this.silenceTimer = setTimeout(() => {
                if (this.voiceState.transcript.trim() !== "") {
                    console.log("3 segundos de silencio. Procesando:", this.voiceState.transcript);
                    // this._onVoiceComplete(this.voiceState.transcript);
                }
            }, 1000);
            }
            this.recognition.onend = () => { 
            // Si el reconocimiento se detiene por error del navegador, lo reiniciamos si seguíamos en modo 'Listening'
                if (this.voiceState.isListening) {
                    this.recognition.start();
                }
            };
        }
    }

    // async _apiIA(text) {
    //     const url = "https://api.groq.com/openai/v1/chat/completions";
    //     // this.productos = await this.orm.searchRead("product.product", [], ["name"]);
    //     // console.log('PRODUCTOS DENTRO DEL HOOK:', this.productos);
    //     // const listaProductos = this.productos
    //     const reglasDinamicas = this.voiceConfigs.map(c => {
    //         const campos = c.fields.map(f => `- Campo técnico: "${f.name}" (el usuario lo llamará: "${f.name_ia || f.name}")`).join("\n");
    //         return `COMANDO: ${c.name}
    //         - Usar modelo: "${c.model_name}"
    //         - Intención: "${c.action_type}"
    //         - Campos a extraer (USA SOLO LOS NOMBRES TÉCNICOS COMO LLAVE EN EL JSON):
    //         ${campos}`;
    //     }).join("\n\n");

    //     const systemPrompt = `
    //         Eres un procesador de lenguaje natural llamado Irene para Odoo 17.
    //         Tu objetivo es transformar dictados con posibles errores en comandos JSON estructurados.
    //         REGLA CRÍTICA DE ACTIVACIÓN:
    //         1. Si el dictado NO comienza o no contiene el nombre "Irene", responde con {"status": "ignored"}.
    //         2. Si el dictado dice "Irene" seguido de una instrucción, procésalo normalmente.

    //         CONFIGURACIÓN ACTUAL DE COMANDOS:
    //         ${reglasDinamicas}

    //         ESTRUCTURA OBLIGATORIA DE RESPUESTA:
    //         {
    //             "status": "success" o "error",
    //             "intent": "create" o "filter",
    //             "model": "nombre.del.modelo.odoo",
    //             "data": {
    //                 "campo_odoo": "valor_extraido"
    //             },
    //             "answer": "Mensaje de respuesta, diciendo brevemente que acción se realizara, ejemplo realizando creación de cliente con nombre: jesus, cedula: 311101361, etc",
    //             "msg": "Envio del mensaje si se cambio el mensaje que se envio en alguna, solo si es necesario",
    //             "reasoning": "Breve explicación de por qué corregiste el texto"
    //         }

    //         REGLAS DE NEGOCIO:
    //         1. CORRECCIÓN: Si el texto tiene algun error de coherencia o que no conste sentido con lo que esta pidiendo en algunas de las palabras puedes modificar la frase.
    //         2. En el objeto "data", las llaves DEBEN ser los nombres técnicos de los campos. Si el usuario dice "nombre", tú escribes "name" (o el nombre técnico que corresponda).
    //         3. Si la persona dice algo como nombre completo, debes buscar si se parece a uno de los nombres de la data, ejemplo en este caso nombre completo se refiere a nombre 
    //     `;

    //     console.log(text)
    //     const body = {
    //         model: "llama-3.1-8b-instant",
    //         messages: [
    //             { 
    //                 role: "system", 
    //                 content: systemPrompt
    //             },
    //             { 
    //                 role: "user", 
    //                 content: `Analiza y estructura este dictado: "${text}"` 
    //             }
    //         ],
    //         response_format: { type: "json_object" }
    //     };

    //     try {
    //         const response = await fetch(url, {
    //             method: "POST",
    //             headers: {
    //                 "Authorization": `Bearer ${apiKey}`,
    //                 "Content-Type": "application/json"
    //             },
    //             body: JSON.stringify(body)
    //         });
            
    //         if (!response.ok) {
    //             const errorDetails = await response.json();
    //             console.error("Detalles del error de Groq:", errorDetails);
    //             throw new Error("Error en la API de Groq");
    //         }
    //         console.log("interim: ", text)
    //         const data = await response.json(); 
    
    //         console.log("Respuesta completa de la API:", data);

    //         const content = data.choices[0].message.content;
    //         const aiData = JSON.parse(content);
            
    //         console.log("Objeto JSON final:", aiData);
            
    //         return aiData;
    //     } catch (error) {
    //         console.error("Fallo al conectar con la IA:", error);
    //         return null;
    //     }
    // }

    async _apiIA(text) {
        // Mantienes tu lógica de reglas dinámicas porque OWL conoce el estado de la UI
        const reglasDinamicas = this.voiceConfigs.map(c => {
            const campos = c.fields.map(f => `- Campo técnico: "${f.name}" (el usuario lo llamará: "${f.name_ia || f.name}")`).join("\n");
            return `COMANDO: ${c.name}\n- Usar modelo: "${c.model_name}"\n- Intención: "${c.action_type}"\n- Campos:\n${campos}`;
        }).join("\n\n");

        try {
            // Llamada al servidor Odoo
            const aiData = await this.rpc('/groq/process_command', {
                text: text,
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
        try {
            if (aiData.intent === 'create') {
                // await this.orm.create(aiData.model, [aiData.data]);
                await this.rpc("/web/dataset/call_kw/voice.command.config/voice_create_record", {
                    model: 'voice.command.config',
                    method: 'voice_create_record',
                    args: [aiData.model, aiData.data],
                    kwargs: {},
                });
                console.log("Registro creado con éxito en", aiData.model);
                if (audioBase64 && !audioBase64.error) {
                    const audio = new Audio("data:audio/mp3;base64," + audioBase64);
                    audio.play();
                } else {
                    console.error("Error al obtener audio:", audioBase64.error);
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
        } catch (error) {
            console.error("Error en el ORM:", error);
        }
    }
        

        async _speak(text) {
            try {
                const audioBase64 = await this.rpc('/fenix/get_audio', {
                    text: text,
                });

                if (audioBase64.error) {
                    console.error("Error desde el servidor:", audioBase64.error);
                    return;
                }
                const audio = new Audio(`data:audio/mpeg;base64,${audioBase64}`);
                audio.play();
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

    // async _speak(text) {
    //     const VOICE_ID = "nbcvT3C2tyOd2OsRAtUf"; // El ID que estabas usando
        
    //     try {
    //         const response = await fetch(`https://api.elevenlabs.io/v1/text-to-speech/${VOICE_ID}`, {
    //             method: 'POST',
    //             headers: {
    //                 'Content-Type': 'application/json',
    //                 'xi-api-key': API_KEY // Asegúrate de que este nombre sea exacto
    //             },
    //             body: JSON.stringify({
    //                 text: text,
    //                 model_id: "eleven_multilingual_v2",
    //                 voice_settings: {
    //                     stability: 0.5,
    //                     similarity_boost: 0.8
    //                 }
    //             })
    //         });

    //         if (!response.ok) {
    //             const errorBody = await response.json();
    //             console.error("Error de ElevenLabs:", errorBody);
    //             // Si falla ElevenLabs, usamos la voz del navegador como respaldo (Backup)
    //             this._speak(text); 
    //             return;
    //         }

    //         const blob = await response.blob();
    //         const url = URL.createObjectURL(blob);
    //         const audio = new Audio(url);
            
    //         audio.oncanplaythrough = () => audio.play();
            
    //         // Limpieza de memoria
    //         audio.onended = () => URL.revokeObjectURL(url);

    //     } catch (error) {
    //         console.error("Error en la llamada a ElevenLabs:", error);
    //         this._speak(text); // Respaldo
    //     }
    // }

    async _onClick() {

        if (!this.recognition) return;
        const SpeechGrammarList = window.SpeechGrammarList || window.webkitSpeechGrammarList;
        if (SpeechGrammarList && this.medicalGrammar) {
            const speechRecognitionList = new SpeechGrammarList();
            speechRecognitionList.addFromString(this.medicalGrammar, 1);
            this.recognition.grammars = speechRecognitionList;
            console.log("Gramática inyectada en el motor de voz");
        }
        if (!this.medicalGrammar && this.productos.length > 0) {
            const productNames = this.productos.map(p => p.name).join(' | ');
            this.medicalGrammar = `#JSGF V1.0; grammar products; public <product> = ${productNames};`;
        }

        this.voiceState.transcript = "Esperando voz...";
        this.voiceState.isListening = true;
        this.recognition.start();
        
        this.closeWizard = this.dialogService.add(VoiceAssistantDialog, {
            title: "Asistente de Voz",
            transcript: this.voiceState, // Pasamos el estado para que se actualice en el wizard
            onClose: () => this.recognition.stop(), 
        });

        this.recognition.onend = async () => {
            this.voiceState.isListening = false;
            let aiData =  await this._apiIA(this.voiceState.transcript);
            // this.voiceState.answer = aiData.answer
            // await this._processCommands(this.voiceState.transcript);
            if (aiData && aiData.status === "success") {
                this.voiceState.answer = aiData.answer;
                // this._speak(aiData.answer);
                await this._processCommands(aiData);
            } else if (aiData && aiData.status === "ignored") {
                console.log("Irene escuchó algo, pero no era para ella.");
                this.voiceState.transcript = ""; // Limpiamos para no confundir
                this.closeWizard(); // Cerramos discretamente
            }
            // Esperamos 2 segundos para que el usuario lea lo que dijo y cerramos
            setTimeout(async() => {
                console.log("Cerrando wizard automáticamente...");
                this.closeWizard();
            }, 1000);
        };
    }
}

VoiceSystray.template = "voice_to_text.VoiceSystray";
registry.category("systray").add("voice_to_text.VoiceAssistant", { Component: VoiceSystray });
VoiceSystray.props = {
    "*": true, // Esto le dice a OWL: "Acepto cualquier prop que me envíes"
};