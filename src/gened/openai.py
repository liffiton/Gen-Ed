# SPDX-FileCopyrightText: 2023 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

from collections.abc import Callable
from dataclasses import dataclass
from functools import wraps
from sqlite3 import Row
from typing import ParamSpec, TypeVar

import openai
from flask import current_app, flash, render_template
from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionMessageParam

from .auth import get_auth
from .db import get_db


class ClassDisabledError(Exception):
    pass


class NoKeyFoundError(Exception):
    pass


class NoTokensError(Exception):
    pass


@dataclass(frozen=True)
class LLMConfig:
    client: AsyncOpenAI
    model: str
    tokens_remaining: int | None = None  # None if current user is not using tokens


def _get_llm(*, use_system_key: bool, spend_token: bool) -> LLMConfig:
    ''' Get model details and an initialized OpenAI client based on the
    arguments and the current user and class.

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
      LLMConfig with an OpenAI client and model name.

    Raises various exceptions in cases where a key and model are not available.
    '''
    db = get_db()

    def make_system_client(tokens_remaining: int | None = None) -> LLMConfig:
        """ Factory function to initialize a default client (using the system key)
            only if/when needed.
        """
        system_model = current_app.config["SYSTEM_MODEL"]
        system_key = current_app.config["OPENAI_API_KEY"]
        return LLMConfig(
            client=AsyncOpenAI(api_key=system_key),
            model=system_model,
            tokens_remaining=tokens_remaining,
        )

    if use_system_key:
        return make_system_client()

    auth = get_auth()

    # Get class data, if there is an active class
    if auth['class_id']:
        class_row = db.execute("""
            SELECT
                classes.enabled,
                COALESCE(consumers.openai_key, classes_user.openai_key) AS openai_key,
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
        """, [auth['class_id']]).fetchone()

        if not class_row['enabled']:
            raise ClassDisabledError

        if not class_row['openai_key']:
            raise NoKeyFoundError

        api_key = class_row['openai_key']
        return LLMConfig(
            client=AsyncOpenAI(api_key=api_key),
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
    """, [auth['user_id']]).fetchone()

    if user_row['auth_provider_name'] == "local":
        return make_system_client()

    tokens = user_row['query_tokens']

    if tokens == 0:
        raise NoTokensError

    if spend_token:
        # user.tokens > 0, so decrement it and use the system key
        db.execute("UPDATE users SET query_tokens=query_tokens-1 WHERE id=?", [auth['user_id']])
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
                flash("You have used all of your free queries.  If you are using this application in a class, please connect using the link from your class for continued access.  Otherwise, you can create a class and add an OpenAI API key or contact us if you want to continue using this application.", "warning")
                return render_template("error.html")

            kwargs['llm'] = llm
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def get_models() -> list[Row]:
    """Enumerate the models available in the database."""
    db = get_db()
    models = db.execute("SELECT * FROM models WHERE active ORDER BY id ASC").fetchall()
    return models


async def get_completion(client: AsyncOpenAI, model: str, prompt: str | None = None, messages: list[ChatCompletionMessageParam] | None = None) -> tuple[dict[str, str], str]:
    '''
    model can be any valid OpenAI model name that can be used via the chat completion API.

    Returns:
       - A tuple containing:
           - An OpenAI response object
           - The response text (stripped)
    '''
    common_error_text = "Error ({error_type}).  Something went wrong with this query.  The error has been logged, and we'll work on it.  For now, please try again."
    try:
        if messages is None:
            assert prompt is not None
            messages = [{"role": "user", "content": prompt}]

        response = await client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.25,
            max_tokens=1000,
        )

        choice = response.choices[0]
        response_txt = choice.message.content or ""

        if choice.finish_reason == "length":  # "length" if max_tokens reached
            response_txt += "\n\n[error: maximum length exceeded]"

        return response.model_dump(), response_txt.strip()

    except openai.APITimeoutError as e:
        err_str = str(e)
        response_txt = "Error (APITimeoutError).  The system timed out producing the response.  Please try again."
        current_app.logger.error(f"OpenAI Timeout: {e}")
    except openai.RateLimitError as e:
        err_str = str(e)
        if "exceeded your current quota" in err_str:
            response_txt = "Error (RateLimitError).  The API key for this class has exceeded its current quota (https://platform.openai.com/docs/guides/rate-limits/usage-tiers).  The instructor should check their API plan and billing details.  Possibly the key is in the free tier, which does not cover the models used here."
        else:
            response_txt = "Error (RateLimitError).  The system is receiving too many requests right now.  Please try again in one minute."
        current_app.logger.error(f"OpenAI RateLimitError: {e}")
    except openai.AuthenticationError as e:
        err_str = str(e)
        response_txt = "Error (AuthenticationError).  The API key set by the instructor for this class is invalid.  The instructor needs to provide a valid API key for this application to work."
        current_app.logger.error(f"OpenAI AuthenticationError: {e}")
    except openai.BadRequestError as e:
        err_str = str(e)
        if "maximum context length" in err_str:
            response_txt = "Error (BadRequestError).  Your query is too long for the model to process.  Please reduce the length of your input."
        else:
            response_txt = common_error_text.format(error_type='BadRequestError')
        current_app.logger.error(f"OpenAI BadRequestError: {e}")
    except openai.APIError as e:
        err_str = str(e)
        response_txt = common_error_text.format(error_type='APIError')
        current_app.logger.error(f"Exception (OpenAI {type(e).__name__}, but I don't handle that specifically yet): {e}")

    return {'error': err_str}, response_txt
