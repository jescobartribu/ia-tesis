/** @odoo-module **/
import { registry } from "@web/core/registry";
import { CharField } from "@web/views/fields/char/char_field";

export class AiSimpleField extends CharField {
    // Heredamos TODO del CharField original para que no falte 'name'
    
    async clickIA() {
        const text = this.props.record.data[this.props.name] || "";
        
        // Tu lógica de fetch
        const response = await fetch("https://api.groq.com/openai/v1/chat/completions", {
            method: "POST",
            headers: { "Authorization": "Bearer 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", "Content-Type": "application/json" },
            body: JSON.stringify({
                model: "llama-3.1-8b-instant",
                messages: [{ role: "user", content: `Estructura esto: ${text}` }]
            })
        });

        const data = await response.json();
        const result = data.choices[0].message.content;

        await this.props.record.update({ [this.props.name]: result });
    }
}


registry.category("fields").add("ai_llama_fill", AiSimpleField);