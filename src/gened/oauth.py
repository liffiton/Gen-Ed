# SPDX-FileCopyrightText: 2023 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

from authlib.integrations.flask_client import (  # type: ignore [import-untyped]
    OAuth,
    OAuthError,
)
from flask import Blueprint, abort, current_app, redirect, request, session, url_for
from flask.app import Flask
from werkzeug.wrappers.response import Response

from .auth import (
    ext_login_update_or_create,
    get_last_class,
    set_session_auth_class,
    set_session_auth_user,
)

GOOGLE_CONF_URL = "https://accounts.google.com/.well-known/openid-configuration"
# Microsoft docs: https://learn.microsoft.com/en-us/azure/active-directory/develop/v2-protocols-oidc
MICROSOFT_CONF_URL = "https://login.microsoftonline.com/common/v2.0/.well-known/openid-configuration"
NEXT_URL_SESSION_KEY = "__gened_next_url"


bp = Blueprint('oauth', __name__, url_prefix="/oauth")
_oauth = OAuth()


def init_app(app: Flask) -> None:
    """Register SSO handlers with authlib.
    Note: _oauth.register() automatically loads client ID and secret from app config (see base.py)
    """
    _oauth.init_app(app)
    conf = app.config
    if "GOOGLE_CLIENT_SECRET" in conf:
        _oauth.register(
            name='google',
            server_metadata_url=GOOGLE_CONF_URL,
            client_kwargs={'scope': 'openid email profile'},
        )
    if "GITHUB_CLIENT_SECRET" in conf:
        _oauth.register(
            name='github',
            api_base_url='https://api.github.com/',
            access_token_url='https://github.com/login/oauth/access_token',
            authorize_url='https://github.com/login/oauth/authorize',
            userinfo_endpoint='https://api.github.com/user',
            client_kwargs={'scope': 'user:email'},
        )
    if "MICROSOFT_CLIENT_SECRET" in conf:
        _oauth.register(
            name='microsoft',
            server_metadata_url=MICROSOFT_CONF_URL,
            client_kwargs={'scope': 'openid email profile'},
        )


@bp.route('/login/<string:provider_name>')
def login(provider_name: str) -> Response:
    client = _oauth.create_client(provider_name)
    if not client:
        abort(404)

    # store next_url in session, as simplest way for it to be accessible in auth() below
    next_url = request.args.get('next')
    if next_url:
        session[NEXT_URL_SESSION_KEY] = next_url

    redirect_uri = url_for('.auth', provider_name=provider_name, _external=True)
    redir = client.authorize_redirect(redirect_uri)
    assert isinstance(redir, Response)
    return redir


@bp.route('/auth/<string:provider_name>')
def auth(provider_name: str) -> Response:
    client = _oauth.create_client(provider_name)
    if not client:
        abort(404)

    try:
        if provider_name == 'microsoft':
            # Microsoft isn't *quite* OIDC compliant:
            #   https://github.com/MicrosoftDocs/azure-docs/issues/38427
            # So this is a bit of a hack that disables checking the 'iss' (issuer) claim.
            # The value in claims_options['iss'] is eventually used as 'option' in
            #   authlib/jose/rfc7519/claims.py : BaseClaims._validate_claim_value()
            # and providing an empty dict makes it skip any validation.
            token = client.authorize_access_token(claims_options={'iss': {}})
        else:
            token = client.authorize_access_token()
    except OAuthError:
        return redirect(url_for("auth.login"))

    user = token.get('userinfo') or client.userinfo()

    if not user.get('email'):
        # On Github, email will be null if user does not share email publicly, but we can enumerate
        # their email addresses using the user api and choose the one they have marked 'primary'
        # [https://github.com/authlib/loginpass/blob/master/loginpass/github.py]
        assert provider_name == 'github'
        response = client.get('user/emails')
        response.raise_for_status()
        data = response.json()
        user['email'] = next(item['email'] for item in data if item['primary'])

    user_normed = {
        'email': user.get('email'),
        'full_name': user.get('name'),
        'auth_name': user.get('login'),
        'ext_id': user.get('sub') or user.get('id')   # 'sub' for OpenID Connect (Google, Microsoft); 'id' for Github
    }

    current_app.logger.debug(f"SSO login: {provider_name=} email='{user_normed['email']}' full_name='{user_normed['full_name']}'")

    # Given 10 tokens by default if creating an account on first login.
    user_row = ext_login_update_or_create(provider_name, user_normed, query_tokens=20)

    # Get their last active class, if there is one (and it still exists and user has active role in it)
    last_class_id = get_last_class(user_row['id'])

    # Now, either the user existed or has been created.  Log them in!
    set_session_auth_user(user_row['id'])
    set_session_auth_class(last_class_id)

    # Redirect to stored next_url (and reset) if one has been stored, else root path
    next_url = session.get(NEXT_URL_SESSION_KEY) or "/"

    # Clear the stored next URL if it is there
    session.pop(NEXT_URL_SESSION_KEY, None)

    return redirect(next_url)
