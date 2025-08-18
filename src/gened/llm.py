# SPDX-FileCopyrightText: 2023 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from functools import wraps
from sqlite3 import Row
from typing import Any, ParamSpec, TypeAlias, TypeVar

from flask import current_app, flash, render_template

from .auth import get_auth
from .db import get_db
from .openai_client import ChatStream, OpenAIChatMessage, OpenAIClient

ChatMessage: TypeAlias = OpenAIChatMessage

DEFAULT_COMPLETION_ARGS: dict[str, Any] = {
    'temperature': 0.25,
    'max_completion_tokens': 10000,
}


@dataclass
class LLM:
    """Manages access to language models with token tracking and lazy client initialization."""
    provider: str
    shortname: str
    model: str
    endpoint: str | None  # if None, use the default OpenAI endpoint
    api_key: str | None
    default_params: dict[str, Any] | None
    active: bool
    tokens_remaining: int | None = None  # None if current user is not using tokens
    _client: OpenAIClient | None = field(default=None, init=False, repr=False)  # Instantiated only when needed

    def make_args(self, extra_args: dict[str, Any] | None) -> dict[str, Any]:
        completion_args = DEFAULT_COMPLETION_ARGS.copy()
        if self.default_params:
            completion_args |= self.default_params
        if extra_args:
            completion_args |= extra_args

        return completion_args

    async def get_completion(self, *, prompt: str | None = None, messages: list[OpenAIChatMessage] | None = None, extra_args: dict[str, Any] | None = None) -> tuple[dict[str, str], str]:
        """Get a completion from the language model.

        Args:
            prompt: A single string to send as a user message [deprecated: use messages]
            messages: A list of chat messages in OpenAI format
            extra_args: A dictionary of additional named arguments to pass to the API

        Only one of prompt or messages should be used in a call.

        The client is lazily instantiated on first use.

        Delegates to OpenAIClient.get_completion() (see openai_client.py)
        """
        assert self.api_key is not None
        if self._client is None:
            self._client = OpenAIClient(self.model, self.api_key, base_url=self.endpoint)

        # handle 'old-style' prompt parameter
        if messages is None:
            assert prompt is not None
            messages = [{"role": "user", "content": prompt}]

        completion_args = self.make_args(extra_args)
        return await self._client.get_completion(messages, completion_args)

    async def stream_completion(self, *, messages: list[OpenAIChatMessage], extra_args: dict[str, Any] | None = None) -> ChatStream:
        """Stream a completion from the language model.

        Args:
            messages: A list of chat messages in OpenAI format
            extra_args: A dictionary of additional named arguments to pass to the API

        The client is lazily instantiated on first use.

        Delegates to OpenAIClient.stream_completion() (see openai_client.py)
        """
        assert self.api_key is not None
        if self._client is None:
            self._client = OpenAIClient(self.model, self.api_key, base_url=self.endpoint)

        completion_args = self.make_args(extra_args)
        return await self._client.stream_completion(messages, completion_args)

    async def get_multi_completion(self, sys_prompt: str, user_prompts: list[str], extra_args: dict[str, Any] | None = None) -> tuple[dict[str, str], str]:
        """Get a completion from the language model
        following a series of prompts from the user.
        """
        messages: list[ChatMessage] = [
            {'role': 'system', 'content': sys_prompt},
        ]

        for user_prompt in user_prompts:
            messages.append({'role': 'user', 'content': user_prompt})
            response, response_txt = await self.get_completion(messages=messages, extra_args=extra_args)
            messages.append({'role': 'assistant', 'content': response_txt})

        return response, response_txt


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

    def make_system_client() -> LLM:
        """ Factory function to initialize a default client (using the system key)
            only if/when needed.
        """
        system_key = current_app.config["SYSTEM_API_KEY"]
        system_model = current_app.config["SYSTEM_MODEL_SHORTNAME"]
        model = get_model(by_shortname=system_model)
        assert model is not None
        assert model.active
        model.api_key = system_key
        return model

    if use_system_key:
        return make_system_client()

    auth = get_auth()

    # Get class data, if there is an active class
    if auth.cur_class is not None:
        class_row = db.execute("""
            SELECT
                classes.enabled,
                COALESCE(consumers.llm_api_key, classes_user.llm_api_key) AS llm_api_key,
                COALESCE(consumers.model_id, classes_user.model_id) AS model_id
            FROM classes
            LEFT JOIN classes_lti
              ON classes.id = classes_lti.class_id
            LEFT JOIN consumers
              ON classes_lti.lti_consumer_id = consumers.id
            LEFT JOIN classes_user
              ON classes.id = classes_user.class_id
            WHERE classes.id = ?
        """, [auth.cur_class.class_id]).fetchone()

        if not class_row['enabled']:
            raise ClassDisabledError

        if not class_row['llm_api_key']:
            raise NoKeyFoundError

        model = get_model(by_id=class_row['model_id'])
        assert model is not None
        model.api_key = class_row['llm_api_key']
        return model

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

    model = make_system_client()
    model.tokens_remaining = tokens
    return model


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


def get_model(*, by_id: int | None = None, by_shortname: str | None = None) -> LLM | None:
    """Get a model from the database either by id (if by_id is set) or by
       shortname (if by_shortname is set).
    """
    db = get_db()
    model_row = db.execute("""
        SELECT
            m.id,
            p.name AS provider,
            m.shortname,
            m.model,
            COALESCE(m.custom_endpoint, p.endpoint) AS endpoint,
            m.default_params,
            m.active
        FROM models AS m
        JOIN llm_providers AS p ON p.id=m.provider_id
        AND (m.id = ? OR m.shortname =?)
        ORDER BY m.id ASC
    """, [by_id, by_shortname]
    ).fetchone()

    if not model_row:
        return None

    default_params = json.loads(model_row['default_params'])

    return LLM(
        provider=model_row['provider'],
        shortname=model_row['shortname'],
        model=model_row['model'],
        endpoint=model_row['endpoint'],
        default_params=default_params,
        active=model_row['active'],
        api_key=None,  # to be filled in later if needed
    )


def get_models(plus_id : int | None = None) -> list[Row]:
    """Get all active language models from the database.
    The plus_id argument can be used to add a currently-selected model to the
    list even if it is not marked as active in the database.
    """
    db = get_db()
    auth = get_auth()

    models = db.execute("""
        SELECT
            m.id,
            p.name AS provider,
            m.shortname,
            m.model,
            COALESCE(m.custom_endpoint, p.endpoint) AS endpoint,
            m.default_params,
            m.active
        FROM models AS m
        JOIN llm_providers AS p ON p.id=m.provider_id
        WHERE
            ( m.active AND (m.scope = 'system' OR m.owner_id = ?) )
            OR m.id = ?
        ORDER BY m.id ASC
    """, [auth.user_id, plus_id]).fetchall()
    return models
