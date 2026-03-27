/** @odoo-module **/
import { patch } from "@web/core/utils/patch";
import { CharField } from "@web/views/fields/char/char_field";
import { TextField } from "@web/views/fields/text/text_field";
import { useState, useRef } from "@odoo/owl"; // Asegúrate de importar esto

const voiceMixin = {
    setup() {
        super.setup();
        // this.state = useState({ isListening: false });
        this.inputRef = useRef("input");
        this.state = useState({
            ghostText: "",
            isFocused: false,
            suggestion: "esta es mi sugerencia fija"
        });
        this.typingTimer = null;

        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        if (SpeechRecognition) {
            this.recognition = new SpeechRecognition();
            this.recognition.lang = 'es-ES';
            this.recognition.continuous = false;

            this.recognition.onresult = (event) => {
                const text = event.results[0][0].transcript;
                if (text) {
                    const fieldName = this.props.name;
                    const currentVal = this.props.record.data[fieldName] || "";
                    const newValue = currentVal + (currentVal ? " " : "") + text;

                    this.props.record.update({ [this.props.name]: newValue });
                    const inputElement = this.inputRef.el;
                    if (inputElement) {
                        inputElement.value = newValue; // Ponemos el texto en el cuadro
                        // Disparamos el evento para que Odoo valide el campo
                        inputElement.dispatchEvent(new Event('input', { bubbles: true }));
                    }
                    // this.render(true);
                    console.log("Contexto de this:", this);
                    console.log("Props actuales:", this.props);
                    console.log("Nuevo valor:", newValue);
                    this.env.services.notification.add("Texto capturado: " + text, { type: "success" });
                    
                }
            };

            this.recognition.onstart = () => { this.state.isListening = true; };
            this.recognition.onend = () => { this.state.isListening = false; };
            this.recognition.onerror = () => { this.state.isListening = false; };
        }
    },

    async _onVoiceIconClick(ev) {
        ev.stopPropagation();
        if (!this.recognition) return;

        if (this.state.isListening) {
            this.recognition.stop();
        } else {
            try {
                // El error ocurría aquí si llamabas start() demasiado rápido
                this.recognition.start();
            } catch (e) {
                console.warn("Reconocimiento ya activo o en proceso de cierre:", e);
            }
        }
    },
    async _onInput(ev) {
        const value = ev.target.value;
        
        // // Si lo que escribes coincide con el inicio de nuestra sugerencia
        // let aiData =  await this._apiIA(value);
        // this.state.ghostText = aiData.message;
        if (!value) {
            this.state.ghostText = "";
            return;
        }


        clearTimeout(this.typingTimer);
        this.typingTimer = setTimeout(async () => {
            // Obtenemos todos los datos actuales del formulario como contexto
            // const recordContext = this.props.record.data; 
            // const aiData = await this._apiIA(value, recordContext);
            // console.log(aiData)
            // if (aiData && aiData.message) {
            //     this.state.ghostText = aiData.message;
            //     console.log(this.state.ghostText)
            // }
            const rawData = this.props.record.data;
            const cleanContext = {};
            for (const key in rawData) {
                const val = rawData[key];
                // Solo enviamos valores que sean texto, números o booleanos simples
                if (typeof val === 'string' || typeof val === 'number' || typeof val === 'boolean') {
                    cleanContext[key] = val;
                } else if (Array.isArray(val) && val.length === 2) {
                    // Si es un Many2one [id, name], enviamos solo el nombre
                    cleanContext[key] = val[1];
                }
            }

            const aiData = await this._apiIA(value, cleanContext);
            console.log('aiData', aiData, 'aidata.mesage', aiData.message)
            
            // Verificamos que aiData exista y tenga la propiedad message
            if (aiData && aiData.message) {
                this.state.ghostText = aiData.message;
                console.log('ghostText:', this.state.ghostText )
                // Guardamos la sugerencia completa para el TAB
                this.state.suggestion = aiData.message; 
            }
        }, 1000);
    },

    _onKeyDown(ev) {
        // Si presionas TAB y hay un texto fantasma
        if (ev.key === "Tab" && this.state.ghostText) {
            ev.preventDefault(); // Evita que el foco salte al siguiente campo
            this._acceptSuggestion();
        }
    },

    _acceptSuggestion() {
        const fullText = this.state.suggestion;
        if (!fullText) return;
        // 1. Actualizamos el registro en Odoo
        this.props.record.update({ [this.props.name]: fullText });

        // 2. Actualizamos el input visualmente
        if (this.inputRef.el) {
            this.inputRef.el.value = fullText;
        }

        // 3. Limpiamos el texto fantasma
        this.state.ghostText = "";
    },
    
    async _apiIA(text, context) {
        const apiKey = "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"; 
        const url = "https://api.groq.com/openai/v1/chat/completions";
        // Convertimos el objeto de contexto a un string legible para la IA
        // const contextSummary = Object.entries(context)
        //     .filter(([_, v]) => v !== false && v !== null) // Filtramos campos vacíos
        //     .map(([k, v]) => `${k}: ${v}`).join(", ");
        const contextStr = JSON.stringify(context);

        const systemPrompt = `
            Eres un procesador de lenguaje natural para Odoo 17.
            CONTEXTO DEL FORMULARIO ACTUAL: { ${contextStr} }
            
            TAREA: Basado en el contexto y lo que el usuario escribe, predice cómo terminaría la frase.
            RESPUESTA: Devuelve un JSON con la llave "message" que contenga la sugerencia COMPLETA.
        `;

        console.log(text)
        const body = {
            model: "llama-3.1-8b-instant",
            messages: [
                { 
                    role: "system", 
                    content: systemPrompt
                },
                { 
                    role: "user", 
                    content: `Texto actual: "${text}"` 
                }
            ],
            response_format: { type: "json_object" }
        };

        try {
            const response = await fetch(url, {
                method: "POST",
                headers: {
                    "Authorization": `Bearer ${apiKey}`,
                    "Content-Type": "application/json"
                },
                body: JSON.stringify(body)
            });
            
            if (!response.ok) {
                const errorDetails = await response.json();
                console.error("Detalles del error de Groq:", errorDetails);
                throw new Error("Error en la API de Groq");
            }
            console.log("interim: ", text)
            const data = await response.json(); 
    
            console.log("Respuesta completa de la API:", data);

            const content = data.choices[0].message.content;
            const aiData = JSON.parse(content);
            
            console.log("Objeto JSON final:", aiData);
            console.log('content:', content )
            
            return aiData;
        } catch (error) {
            console.error("Fallo al conectar con la IA:", error);
            return null;
        }
    }
};

patch(CharField.prototype, voiceMixin);
patch(TextField.prototype, voiceMixin);