from odoo import models, api

def action_open_ia_disaggregate_wizard(self):
    self.ensure_one()
    config_id = self.env.context.get('active_config_id')
    config = self.env['voice.disaggregation.config'].browse(config_id)
    
    source_text = getattr(self, config.field_id.name)

    return {
        'name': f'Irene IA: {config.name}',
        'type': 'ir.actions.act_window',
        'res_model': 'ia.disaggregate.wizard',
        'view_mode': 'form',
        'target': 'new',
        'context': {
            'default_config_id': config.id,
            'default_source_text': source_text,
            'default_res_model': self._name,
            'default_res_id': self.id,
        }
    }

# Inyección en la clase base
if not hasattr(models.Model, 'action_open_ia_disaggregate_wizard'):
    models.Model.action_open_ia_disaggregate_wizard = action_open_ia_disaggregate_wizard