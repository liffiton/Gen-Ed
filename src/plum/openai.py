import asyncio
from functools import wraps

from flask import current_app, flash, render_template
import openai

from .db import get_db
from .auth import get_auth


# When this is provided as an API key to get_completion(), no API call will be made.
# The function will sleep to simulate a request, then return test data.
TEST_API_KEY = '__TESTING__'


class ClassDisabledError(Exception):
    pass


class NoKeyFoundError(Exception):
    pass


class NoTokensError(Exception):
    pass


def _get_llm(use_system_key):
    ''' Get model details and an OpenAI key based on the arguments and the
    current user and class.

    Procedure, depending on arguments, user, and class:
      1) If use_system_key is True, the system API key is always used with no checks.
      2) If there is a current class, and it is enabled, then its model+API key is used:
         a) LTI class config is in the linked LTI consumer.
         b) User class config is in the user class.
         c) If there is a current class but it is disabled or has no key, raise an error.
      3) If the user is a local-auth user, the system API key and GPT-3.5 is used.
      4) Otherwise, we use tokens.
           The user must have 1 or more tokens remaining.
             If they have 0 tokens, raise an error.
             Otherwise, their token count is decremented, and the system API
             key is used with GPT-3.5.

    Returns:
      Dictionary with keys 'key', 'text_model', and 'chat_model'.

    Raises various exceptions in cases where a key and model are not available.
    '''
    system_default = {
        'key': current_app.config["OPENAI_API_KEY"],
        'text_model': 'text-davinci-003',
        'chat_model': 'gpt-3.5-turbo',
    }

    if use_system_key:
        return system_default

    auth = get_auth()
    db = get_db()

    # Get class data, if there is an active class
    if auth['class_id']:
        class_row = db.execute("""
            SELECT
                classes.enabled,
                COALESCE(consumers.openai_key, classes_user.openai_key) AS openai_key,
                COALESCE(consumers.model_id, classes_user.model_id) AS _model_id,
                models.text_model,
                models.chat_model
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
            raise ClassDisabledError()
        elif not class_row['openai_key']:
            raise NoKeyFoundError()
        else:
            return {
                'key': class_row['openai_key'],
                'text_model': class_row['text_model'],
                'chat_model': class_row['chat_model'],
            }

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
        return system_default

    tokens = user_row['query_tokens']
    if tokens == 0:
        raise NoTokensError()

    # user.tokens > 0, so decrement it and use the system key
    db.execute("UPDATE users SET query_tokens=query_tokens-1 WHERE id=?", [auth['user_id']])
    db.commit()
    return system_default


def with_llm(use_system_key=False):
    '''Decorate a view function that requires an LLM and API key.

    Assigns an 'llm_dict' named argument.

    Checks that the current user has access to an LLM and API key (configured
    in an LTI consumer or user-created class), then passes the appropriate
    model info and API key to the wrapped view function, if granted.

    If use_system_key is True, all users can access this, and they use the
    system API key and GPT-3.5.
    '''
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            try:
                llm_dict = _get_llm(use_system_key)
                assert isinstance(llm_dict['key'], str) and llm_dict['key'] != ''
            except ClassDisabledError:
                flash("Error: The current class is archived or disabled.  Request cannot be submitted.")
                return render_template("error.html")
            except NoKeyFoundError:
                flash("Error: No API key set.  Request cannot be submitted.")
                return render_template("error.html")
            except NoTokensError:
                flash("You have used all of your free tokens.  Please create a class and add an OpenAI API key or contact us if you want to continue using this application.", "warning")
                return render_template("error.html")

            return f(*args, **kwargs, llm_dict=llm_dict)
        return decorated_function
    return decorator


def get_models():
    """Enumerate the models available in the database."""
    db = get_db()
    models = db.execute("SELECT * FROM models ORDER BY id ASC").fetchall()
    return models


async def get_completion(api_key, prompt=None, messages=None, model=None, n=1, score_func=None):
    '''
    model can be any valid OpenAI model name.
    If it is 'text-davinci-003', it is treated as a text completion model.
    Otherwise, it's used as a chat completion model.

    Returns:
       - A tuple containing:
           - An OpenAI response object
           - The response text (stripped)
    '''
    assert prompt is None or messages is None
    if model == 'text-davinci-003':
        assert prompt is not None

    if api_key == TEST_API_KEY:
        await asyncio.sleep(2)  # simulate a 2 second delay for a network request
        return "TEST DATA: " + "x "*500, "TEST DATA: " + "x "*500,

    common_error_text = "Error ({error_type}).  Something went wrong with this query.  The error has been logged, and we'll work on it.  For now, please try again."
    try:
        if model == 'text-davinci-003':
            response = await openai.Completion.acreate(
                api_key=api_key,
                model=model,
                prompt=prompt,
                temperature=0.25,
                max_tokens=1000,
                n=n,
                # TODO: add user= parameter w/ unique ID of user (e.g., hash of username+email or similar)
            )
            get_text = lambda choice: choice.text  # noqa
        else:
            if messages is None:
                messages = [{"role": "user", "content": prompt}]
            response = await openai.ChatCompletion.acreate(
                api_key=api_key,
                model=model,
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
        response = str(e)
        response_txt = common_error_text.format(error_type='APIError')
        current_app.logger.error(f"OpenAI APIError: {e}")
    except openai.error.Timeout as e:
        response = str(e)
        response_txt = common_error_text.format(error_type='Timeout')
        current_app.logger.error(f"OpenAI Timeout: {e}")
    except openai.error.ServiceUnavailableError as e:
        current_app.logger.error(e)
        response = str(e)
        response_txt = common_error_text.format(error_type='ServiceUnavailableError')
        current_app.logger.error(f"OpenAI ServiceUnavailableError: {e}")
    except openai.error.RateLimitError as e:
        response = str(e)
        response_txt = "Error (RateLimitError).  The system is receiving too many requests right now.  Please try again in one minute."
        current_app.logger.error(f"OpenAI RateLimitError: {e}")
    except openai.error.AuthenticationError as e:
        response = str(e)
        response_txt = "Error (AuthenticationError).  The API key is invalid, expired, or revoked.  If you are a student, please inform the instructor for your class."
        current_app.logger.error(f"OpenAI AuthenticationError: {e}")
    except openai.error.InvalidRequestError as e:
        response = str(e)
        if "maximum context length" in response:
            response_txt = "Error (InvalidRequestError).  Your query is too long for the model to process.  Please reduce the length of your input."
        else:
            response_txt = common_error_text.format(error_type='InvalidRequestError')
        current_app.logger.error(f"OpenAI InvalidRequestError: {e}")
    except Exception as e:
        response = str(e)
        response_txt = common_error_text.format(error_type='Exception')
        current_app.logger.error(f"Exception (OpenAI {type(e).__name__}, but I don't handle that specifically yet): {e}")

    return response, response_txt.strip()
