# SPDX-FileCopyrightText: 2023 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

from collections.abc import Callable
from dataclasses import dataclass, field
from functools import wraps
from sqlite3 import Row
from typing import Any, Literal, ParamSpec, TypeAlias, TypeVar

from flask import current_app, flash, render_template

from .auth import get_auth
from .db import get_db
from .openai_client import OpenAIChatMessage, OpenAIClient

LLMProvider: TypeAlias = Literal['google', 'openai']
ChatMessage: TypeAlias = OpenAIChatMessage


def _get_client(provider: LLMProvider, model: str, api_key: str) -> OpenAIClient:
    """Create and configure an OpenAI-compatible client for the given provider.

    Args:
        provider: The LLM provider to use
        model: The model identifier
        api_key: The API key for authentication

    Returns:
        A configured OpenAIClient instance using the appropriate base URL for the provider
    """
    match provider:
        case 'google':
            # https://ai.google.dev/gemini-api/docs/openai
            return OpenAIClient(model, api_key, base_url="https://generativelanguage.googleapis.com/v1beta/openai/")
        case 'openai':
            return OpenAIClient(model, api_key)


@dataclass
class LLM:
    """Manages access to language models with token tracking and lazy client initialization."""
    provider: LLMProvider
    model: str
    api_key: str
    tokens_remaining: int | None = None  # None if current user is not using tokens
    _client: OpenAIClient | None = field(default=None, init=False, repr=False)  # Instantiated only when needed

    async def get_completion(self, prompt: str | None = None, messages: list[OpenAIChatMessage] | None = None, extra_args: dict[str, Any] | None = None) -> tuple[dict[str, str], str]:
        """Get a completion from the language model.

        The client is lazily instantiated on first use.

        Delegates to OpenAIClient.get_completion() (see openai_client.py)
        """
        if self._client is None:
            self._client = _get_client(self.provider, self.model, self.api_key)
        return await self._client.get_completion(prompt, messages, extra_args)


class ClassDisabledError(Exception):
    pass

class NoKeyFoundError(Exception):
    pass

class NoTokensError(Exception):
    pass

def _get_llm(*, use_system_key: bool, spend_token: bool) -> LLM:
    ''' Get an LLM object configured based on the arguments and the current
    context (user and class).

    Procedure, depending on arguments, user, and class:
      1) If use_system_key is True, the system API key is always used with no checks.
      2) If there is a current class, and it is enabled, then its model+API key is used:
         a) LTI class config is in the linked LTI consumer.
         b) User class config is in the user class.
         c) If there is a current class but it is disabled or has no key, raise an error.
      3) If the user is a local-auth user, the system API key and model is used.
      4) Otherwise, we use tokens and the system API key / model.
           If spend_token is True, the user must have 1 or more tokens remaining.
             If they have 0 tokens, raise an error.
             Otherwise, their token count is decremented.

    Returns:
      LLM object.

    Raises various exceptions in cases where a key and model are not available.
    '''
    db = get_db()

    def make_system_client(tokens_remaining: int | None = None) -> LLM:
        """ Factory function to initialize a default client (using the system key)
            only if/when needed.
        """
        system_key = current_app.config["OPENAI_API_KEY"]
        system_model = current_app.config["SYSTEM_MODEL"]
        return LLM(
            provider='openai',
            api_key=system_key,
            model=system_model,
            tokens_remaining=tokens_remaining,
        )

    if use_system_key:
        return make_system_client()

    auth = get_auth()

    # Get class data, if there is an active class
    if auth.cur_class is not None:
        class_row = db.execute("""
            SELECT
                classes.enabled,
                COALESCE(consumers.llm_api_key, classes_user.llm_api_key) AS llm_api_key,
                COALESCE(consumers.model_id, classes_user.model_id) AS _model_id,
                models.model
            FROM classes
            LEFT JOIN classes_lti
              ON classes.id = classes_lti.class_id
            LEFT JOIN consumers
              ON classes_lti.lti_consumer_id = consumers.id
            LEFT JOIN classes_user
              ON classes.id = classes_user.class_id
            LEFT JOIN models
              ON models.id = _model_id
            WHERE classes.id = ?
        """, [auth.cur_class.class_id]).fetchone()

        if not class_row['enabled']:
            raise ClassDisabledError

        if not class_row['llm_api_key']:
            raise NoKeyFoundError

        return LLM(
            provider='openai',
            api_key=class_row['llm_api_key'],
            model=class_row['model'],
        )

    # Get user data for tokens, auth_provider
    user_row = db.execute("""
        SELECT
            users.query_tokens,
            auth_providers.name AS auth_provider_name
        FROM users
        JOIN auth_providers
          ON users.auth_provider = auth_providers.id
        WHERE users.id = ?
    """, [auth.user_id]).fetchone()

    if user_row['auth_provider_name'] == "local":
        return make_system_client()

    tokens = user_row['query_tokens']

    if tokens == 0:
        raise NoTokensError

    if spend_token:
        # user.tokens > 0, so decrement it and use the system key
        db.execute("UPDATE users SET query_tokens=query_tokens-1 WHERE id=?", [auth.user_id])
        db.commit()
        tokens -= 1

    return make_system_client(tokens_remaining = tokens)


# For decorator type hints
P = ParamSpec('P')
R = TypeVar('R')


def with_llm(*, use_system_key: bool = False, spend_token: bool = False) -> Callable[[Callable[P, R]], Callable[P, str | R]]:
    '''Decorate a view function that requires an LLM and API key.

    Assigns an 'llm' named argument.

    Checks that the current user has access to an LLM and API key (configured
    in an LTI consumer or user-created class), then passes the appropriate
    LLM config to the wrapped view function, if granted.

    Arguments:
      use_system_key: If True, all users can access this, and they use the
                      system API key and model.
      spend_token:    If True *and* the user is using tokens, then check
                      that they have tokens remaining and decrement their
                      tokens.
    '''
    def decorator(f: Callable[P, R]) -> Callable[P, str | R]:
        @wraps(f)
        def decorated_function(*args: P.args, **kwargs: P.kwargs) -> str | R:
            try:
                llm = _get_llm(use_system_key=use_system_key, spend_token=spend_token)
            except ClassDisabledError:
                flash("Error: The current class is archived or disabled.")
                return render_template("error.html")
            except NoKeyFoundError:
                flash("Error: No API key set.  An API key must be set by the instructor before this page can be used.")
                return render_template("error.html")
            except NoTokensError:
                flash("You have used all of your free queries.  If you are using this application in a class, please connect using the link from your class for continued access.  Otherwise, you can create a class and add an API key or contact us if you want to continue using this application.", "warning")
                return render_template("error.html")

            kwargs['llm'] = llm
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def get_models() -> list[Row]:
    """Get all active language models from the database."""
    db = get_db()
    models = db.execute("SELECT * FROM models WHERE active ORDER BY id ASC").fetchall()
    return models
