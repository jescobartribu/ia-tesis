from odoo import api, fields, models, tools, SUPERUSER_ID, _, Command
from odoo.addons.base.models.ir_model import MODULE_UNINSTALL_FLAG
from odoo.exceptions import AccessDenied, AccessError, UserError, ValidationError
from odoo.http import request, DEFAULT_LANG
from odoo.osv import expression
from odoo.service.db import check_super
from passlib.context import CryptContext as _CryptContext
from psycopg2 import sql
import binascii
import os
import logging

_logger = logging.getLogger(__name__)


class CryptContext:
    def __init__(self, *args, **kwargs):
        self.__obj__ = _CryptContext(*args, **kwargs)

    @property
    def encrypt(self):
        # deprecated alias
        return self.hash

    def copy(self):
        """
            The copy method must create a new instance of the
            ``CryptContext`` wrapper with the same configuration
            as the original (``__obj__``).

            There are no need to manage the case where kwargs are
            passed to the ``copy`` method.

            It is necessary to load the original ``CryptContext`` in
            the new instance of the original ``CryptContext`` with ``load``
            to get the same configuration.
        """
        other_wrapper = CryptContext(_autoload=False)
        other_wrapper.__obj__.load(self.__obj__)
        return other_wrapper

    @property
    def hash(self):
        return self.__obj__.hash

    @property
    def identify(self):
        return self.__obj__.identify

    @property
    def verify(self):
        return self.__obj__.verify

    @property
    def verify_and_update(self):
        return self.__obj__.verify_and_update

    def schemes(self):
        return self.__obj__.schemes()

    def update(self, **kwargs):
        if kwargs.get("schemes"):
            assert isinstance(kwargs["schemes"], str) or all(isinstance(s, str) for s in kwargs["schemes"])
        return self.__obj__.update(**kwargs)


# API keys support
API_KEY_SIZE = 20 # in bytes
INDEX_SIZE = 8 # in hex digits, so 4 bytes, or 20% of the key
KEY_CRYPT_CONTEXT = CryptContext(
    # default is 29000 rounds which is 25~50ms, which is probably unnecessary
    # given in this case all the keys are completely random data: dictionary
    # attacks on API keys isn't much of a concern
    ['pbkdf2_sha512'], pbkdf2_sha512__rounds=6000,
)


class ResUsers(models.Model):
    _inherit = 'res.users'

    token_external = fields.Char("External API Key")

    def api_key_wizard_token_user(self):
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'res.users.apikeys.description.external',
            'name': 'New API Key',
            'target': 'new',
            'context': {
                'default_user_id': self.id,
            },
            'views': [(False, 'form')],
        }


class ResUsersApiKeys(models.Model):
    _inherit = 'res.users.apikeys'

    def _generate_token_user(self, scope, name, user_id=None):
        """Generates an api key.
        :param str scope: the scope of the key. If None, the key will give access to any rpc.
        :param str name: the name of the key, mainly intended to be displayed in the UI.
        :return: str: the key.

        """
        # no need to clear the LRU when *adding* a key, only when removing
        k = binascii.hexlify(os.urandom(API_KEY_SIZE)).decode()
        self.env.cr.execute("""
        INSERT INTO {table} (name, user_id, scope, key, index)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id
        """.format(table=self._table),
        [name, user_id.id, scope, KEY_CRYPT_CONTEXT.hash(k), k[:INDEX_SIZE]])

        ip = request.httprequest.environ['REMOTE_ADDR'] if request else 'n/a'
        _logger.info("External User API Key generated: scope: <%s> for '%s' (#%s) from %s",
            scope, user_id.login, user_id.id, ip)

        return k

    def remove_token(self):
        return self._remove()

    def resend_token_by_email(self):
        template = self.env.ref('external_salesperson.email_template_api_key', raise_if_not_found=False)
        if not template:
            raise UserError(_("The email template for sending API keys is missing. Please contact your administrator."))

        compose = self.env["mail.compose.message"].sudo().create({
            'composition_mode': 'comment',
            # 'views': [(4, compose_form_id)],
            # 'view_mode': 'form',
            'template_id': template.id,
            'model': 'res.users',
            'res_ids': [self.user_id.id],
            # 'use_template': bool(template),
        })

        action = {
            "type": "ir.actions.act_window",
            "res_model": "mail.compose.message",
            "res_id": compose.id,
            "target": "new",
            "view_mode": "form",
            "context": {
                'default_model': 'res.users',
                'active_model': 'res.users',
                'active_id': self.user_id.id,
                'default_res_ids': [self.user_id.id],
                'default_use_template': bool(template),
                'default_template_id': template.id,
                'default_composition_mode': 'comment',
                'force_email': True,
            },
        }
        return action

class APIKeyDescriptionExternal(models.TransientModel):
    _name = 'res.users.apikeys.description.external'
    _description = 'API Key Description External'

    name = fields.Char("Description", required=True)
    user_id = fields.Many2one('res.users', string="User", required=True)

    def make_key(self):
        # only create keys for users who can delete their keys

        description = self.sudo()
        k = self.env['res.users.apikeys']._generate_token_user(None, self.sudo().name, self.user_id)
        description.user_id.write({'token_external': k})
        description.unlink()

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'res.users.apikeys.show',
            'name': _('API Key Ready'),
            'views': [(False, 'form')],
            'target': 'new',
            'context': {
                'default_key': k,
            }
        }

    def send_key_by_email(self):
        
        description = self.sudo()
        k = self.env['res.users.apikeys']._generate_token_user(None, self.sudo().name, self.user_id)
        user_id = description.user_id
        user_id.write({'token_external': k})
        description.unlink()

        template = self.env.ref('external_salesperson.email_template_api_key', raise_if_not_found=False)
        if not template:
            raise UserError(_("The email template for sending API keys is missing. Please contact your administrator."))

        compose = self.env["mail.compose.message"].sudo().create({
            'composition_mode': 'comment',
            # 'views': [(4, compose_form_id)],
            # 'view_mode': 'form',
            'template_id': template.id,
            'model': 'res.users',
            'res_ids': [user_id.id],
            # 'use_template': bool(template),
        })

        action = {
            "type": "ir.actions.act_window",
            "res_model": "mail.compose.message",
            "res_id": compose.id,
            "target": "new",
            "view_mode": "form",
            "context": {
                'default_model': 'res.users',
                'active_model': 'res.users',
                'active_id': user_id.id,
                'default_res_ids': [user_id.id],
                'default_use_template': bool(template),
                'default_template_id': template.id,
                'default_composition_mode': 'comment',
                'force_email': True,
            },
        }
        return action