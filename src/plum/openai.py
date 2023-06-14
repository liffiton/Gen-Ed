from functools import wraps

from flask import current_app, flash, render_template
import openai

from .db import get_db
from .auth import get_session_auth


class NoTokensError(Exception):
    pass


class NoKeyFoundError(Exception):
    pass


def _get_openai_key(use_token, use_system_key):
    ''' Get an OpenAI key based on the arguments and the current user and class.

    Procedure, depending on arguments, user, and class:
      1) If use_system_key is True, the system API key is always used with no checks.
      2) If use_token is True, then:
         a) If the user's token column is Null, then fall through to 3).
         b) Otherwise, the user must have 1 or more tokens remaining.
            If they have 0 tokens, return an error.
            Otherwise, their token count is decremented, and the system API key is used.
      3) If there is a current class, and it is enabled, then its API key is used:
         a) LTI class keys are in the linked LTI consumer.
         b) User class keys are in the user class.
      4) If the user is a local-auth user, the system API key is used.
    '''
    if use_system_key:
        return current_app.config["OPENAI_API_KEY"]

    # Get user data for tokens, auth_provider
    auth = get_session_auth()
    db = get_db()
    user_row = db.execute("""
        SELECT
            users.query_tokens,
            auth_providers.name AS auth_provider_name
        FROM users
        JOIN auth_providers
          ON users.auth_provider = auth_providers.id
        WHERE users.id = ?
    """, [auth['user_id']]).fetchone()

    if use_token:
        tokens = user_row['query_tokens']
        if tokens is not None:
            if tokens == 0:
                raise NoTokensError()
            # user.tokens > 0, so decrement it and use the system key
            db.execute("UPDATE users SET query_tokens=query_tokens-1 WHERE id=?", [auth['user_id']])
            db.commit()
            return current_app.config["OPENAI_API_KEY"]

        # user.tokens is None, so fall through

    if auth['class_id']:
        class_row = db.execute("""
            SELECT
                classes.enabled,
                COALESCE(consumers.openai_key, classes_user.openai_key) AS openai_key
            FROM classes
            LEFT JOIN classes_lti
              ON classes.id = classes_lti.class_id
            LEFT JOIN consumers
              ON classes_lti.lti_consumer_id = consumers.id
            LEFT JOIN classes_user
              ON classes.id = classes_user.class_id
            WHERE classes.id = ?
        """, [auth['class_id']]).fetchone()

        if class_row['enabled'] and class_row['openai_key']:
            return class_row['openai_key']

    if user_row['auth_provider_name'] == "local":
        return current_app.config["OPENAI_API_KEY"]

    raise NoKeyFoundError()


def with_openai_key(use_token=False, use_system_key=False):
    '''Decorate a view function that requires an API key.

    Checks that the current user has access to an API key, then passes
    the appropriate API key to the wrapped view function, if granted.

    If use_token is True, users with tokens must spend one token to use this.

    If use_system_key is True, all users can access this, and they use the
    system API key.
    '''
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            try:
                api_key = _get_openai_key(use_token, use_system_key)
                assert isinstance(api_key, str) and api_key != ''
            except NoTokensError:
                flash("You have used all of your query tokens.  Please use the contact form at the bottom of the page if you want to continue using CodeHelp.", "warning")
                return render_template("error.html")
            except NoKeyFoundError:
                flash("Error: No API key set.  Request cannot be submitted.")
                return render_template("error.html")

            return f(*args, **kwargs, api_key=api_key)
        return decorated_function
    return decorator


async def get_completion(api_key, prompt=None, messages=None, model='turbo', n=1, score_func=None):
    '''
    model can be either 'davinci' or 'turbo'

    Returns:
       - A tuple containing:
           - An OpenAI response object
           - The response text (stripped)
    '''
    assert prompt is None or messages is None
    if model == 'davinci':
        assert prompt is not None

    try:
        if model == 'davinci':
            response = await openai.Completion.acreate(
                api_key=api_key,
                model="text-davinci-003",
                prompt=prompt,
                temperature=0.25,
                max_tokens=1000,
                n=n,
                # TODO: add user= parameter w/ unique ID of user (e.g., hash of username+email or similar)
            )
            get_text = lambda choice: choice.text  # noqa
        elif model == 'turbo':
            if messages is None:
                messages = [{"role": "user", "content": prompt}]
            response = await openai.ChatCompletion.acreate(
                api_key=api_key,
                model="gpt-3.5-turbo",
                messages=messages,
                temperature=0.25,
                max_tokens=1000,
                n=n,
                # TODO: add user= parameter w/ unique ID of user (e.g., hash of username+email or similar)
            )
            get_text = lambda choice: choice.message['content']  # noqa

        if n > 1:
            best_choice = max(response.choices, key=lambda choice: score_func(get_text(choice)))
        else:
            best_choice = response.choices[0]
        response_txt = get_text(best_choice)

        response_reason = best_choice.finish_reason  # e.g. "length" if max_tokens reached

        if response_reason == "length":
            response_txt += "\n\n[error: maximum length exceeded]"

    except openai.error.APIError as e:
        current_app.logger.error(e)
        response = str(e)
        response_txt = "Error (APIError).  Something went wrong on our side.  Please try again, and if it repeats, let us know using the contact form at the bottom of the page."
        pass
    except openai.error.Timeout as e:
        current_app.logger.error(e)
        response = str(e)
        response_txt = "Error (Timeout).  Something went wrong on our side.  Please try again, and if it repeats, let us know using the contact form at the bottom of the page."
        pass
    except openai.error.ServiceUnavailableError as e:
        current_app.logger.error(e)
        response = str(e)
        response_txt = "Error (ServiceUnavailableError).  Something went wrong on our side.  Please try again, and if it repeats, let us know using the contact form at the bottom of the page."
        pass
    except openai.error.RateLimitError as e:
        current_app.logger.error(e)
        response = str(e)
        response_txt = "Error (RateLimitError).  The system is receiving too many requests right now.  Please try again in one minute.  If it does not resolve, please let us know using the contact form at the bottom of the page."
        pass
    except Exception as e:
        current_app.logger.error(e)
        response = str(e)
        response_txt = "Error (Exception).  Something went wrong on our side.  Please try again, and if it repeats, let us know using the contact form at the bottom of the page."
        pass

    return response, response_txt.strip()
