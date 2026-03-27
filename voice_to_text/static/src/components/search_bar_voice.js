/** @odoo-module **/
import { patch } from "@web/core/utils/patch";
import { SearchBar } from "@web/search/search_bar/search_bar";
import { useState, useRef } from "@odoo/owl";

patch(SearchBar.prototype, {
    setup() {
        super.setup();
        this.voiceState = useState({ isListening: false });
        // Referencia al input de búsqueda de Odoo
        this.searchInputRef = useRef("main-input");

        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        if (SpeechRecognition) {
            this.recognition = new SpeechRecognition();
            this.recognition.lang = 'es-ES';

            this.recognition.onresult = (event) => {
                let text = event.results[0][0].transcript.toLowerCase();
                console.log("🎙️ Comando recibido:", text);

                // --- PROCESADOR DE COMANDOS ---
                let searchTerm = text;

                // Ejemplo: "filtro orden número 10" -> Resultado: "10"
                if (text.includes("orden") || text.includes("order")) {
                    searchTerm = text.split(/orden|order/).pop().replace(/número|numero|nº/g, "").trim();
                } 
                // Ejemplo: "filtro proveedor Mitchell Admin" -> Resultado: "Mitchell Admin"
                else if (text.includes("proveedor") || text.includes("vendedor")) {
                    searchTerm = text.split(/proveedor|vendedor/).pop().trim();
                }
                // Ejemplo: "buscar producto silla" -> Resultado: "silla"
                else if (text.includes("buscar") || text.includes("producto")) {
                    searchTerm = text.split(/buscar|producto/).pop().trim();
                }

                this._executeVoiceSearch(searchTerm);
                // const text = event.results[0][0].transcript;
                // if (text) {
                //     // En la barra de búsqueda, Odoo usa un input que dispara 
                //     // la búsqueda al escribir.
                //     const inputEl = document.querySelector('.o_searchview_input');
                //     if (inputEl) {
                //         inputEl.value = text;
                //         // Disparamos 'input' para que Odoo filtre los productos
                //         inputEl.dispatchEvent(new Event('input', { bubbles: true }));
                //         // Opcional: Disparar 'keydown' Enter para ejecutar la búsqueda
                //         inputEl.dispatchEvent(new KeyboardEvent('keydown', {
                //             key: 'Enter',
                //             code: 'Enter',
                //             keyCode: 13,
                //             bubbles: true
                //         }));
                //     }
                // }
            };

            this.recognition.onstart = () => { this.voiceState.isListening = true; };
            this.recognition.onend = () => { this.voiceState.isListening = false; };
        }
    },
    _executeVoiceSearch(term) {
        const inputEl = document.querySelector('.o_searchview_input');
        if (inputEl && term) {
            inputEl.value = term;
            // Notificamos a Odoo del cambio
            inputEl.dispatchEvent(new Event('input', { bubbles: true }));
            
            // Simulamos la tecla ENTER para ejecutar la búsqueda inmediatamente
            setTimeout(() => {
                inputEl.dispatchEvent(new KeyboardEvent('keydown', {
                    key: 'Enter', code: 'Enter', keyCode: 13, bubbles: true
                }));
            }, 200);
            
            console.log("🔍 Buscando automáticamente:", term);
        }
    },

    _onVoiceSearchClick(ev) {
        ev.stopPropagation();
        if (this.voiceState.isListening) {
            this.recognition.stop();
        } else {
            this.recognition.start();
        }
    }
});

