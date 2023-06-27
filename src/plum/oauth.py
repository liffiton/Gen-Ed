from flask import Blueprint, abort, current_app, redirect, request, session, url_for
from authlib.integrations.flask_client import OAuth

from .auth import ext_login_update_or_create, set_session_auth


GOOGLE_CONF_URL = "https://accounts.google.com/.well-known/openid-configuration"
NEXT_URL_SESSION_KEY = "__plum_next_url"


bp = Blueprint('oauth', __name__, url_prefix="/oauth")
_oauth = OAuth()


def init_app(app):
    _oauth.init_app(app)
    _oauth.register(  # automatically loads client ID and secret from app config (see base.py)
        name='google',
        server_metadata_url=GOOGLE_CONF_URL,
        client_kwargs={'scope': 'openid email profile'},
    )
    _oauth.register(
        name='github',
        api_base_url='https://api.github.com/',
        access_token_url='https://github.com/login/oauth/access_token',
        authorize_url='https://github.com/login/oauth/authorize',
        userinfo_endpoint='https://api.github.com/user',
        client_kwargs={'scope': 'user:email'},
    )


@bp.route('/login/<string:provider_name>')
def login(provider_name):
    client = _oauth.create_client(provider_name)
    if not client:
        abort(404)

    # store next_url in session, as simplest way for it to be accessible in auth() below
    next_url = request.args.get('next')
    if next_url:
        session[NEXT_URL_SESSION_KEY] = next_url

    redirect_uri = url_for('.auth', provider_name=provider_name, _external=True)
    return client.authorize_redirect(redirect_uri)


@bp.route('/auth/<string:provider_name>')
def auth(provider_name):
    client = _oauth.create_client(provider_name)
    if not client:
        abort(404)

    client.authorize_access_token()
    user = client.userinfo()

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
        'ext_id': user.get('sub') or user.get('id')   # 'sub' for OpenID Connect (Google); 'id' for Github
    }

    current_app.logger.info(f"SSO login: {provider_name=} {user_normed=}")

    # Given 10 tokens by default if creating an account on first login.
    user_row = ext_login_update_or_create(provider_name, user_normed, query_tokens=10)

    # Now, either the user existed or has been created.  Log them in!
    set_session_auth(user_row['id'], user_row['display_name'])

    # Redirect to stored next_url (and reset) if one has been stored, else root path
    next_url = session.get(NEXT_URL_SESSION_KEY) or "/"

    # Clear the stored next URL if it is there
    session.pop(NEXT_URL_SESSION_KEY, None)

    return redirect(next_url)
