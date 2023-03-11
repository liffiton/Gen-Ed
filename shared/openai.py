from flask import current_app
import openai

from shared.db import get_db
from shared.auth import get_session_auth


def set_openai_key():
    '''Set the openai API key, using the key stored for the current consumer
       or else use the default key in the config for non-LTI users.

    Returns: True if a valid-looking key is found.
    '''
    db = get_db()
    auth = get_session_auth()
    if auth['lti'] is None:
        # default key for non-LTI users
        key = current_app.config["OPENAI_API_KEY"]
    else:
        consumer_row = db.execute("SELECT openai_key FROM consumers WHERE lti_consumer=?", [auth['lti']['consumer']]).fetchone()
        key = consumer_row['openai_key']

    looks_valid = isinstance(key, str) and len(key) > 40

    if looks_valid:
        openai.api_key = key
    else:
        openai.api_key = None

    return looks_valid


async def get_completion(prompt, model='turbo', n=1, score_func=None):
    '''
    model can be either 'davinci' or 'turbo'
    '''
    try:
        if model == 'davinci':
            response = await openai.Completion.acreate(
                model="text-davinci-003",
                prompt=prompt,
                temperature=0.25,
                max_tokens=1000,
                n=n,
                # TODO: add user= parameter w/ unique ID of user (e.g., hash of username+email or similar)
            )
            get_text = lambda choice: choice.text  # noqa
        elif model == 'turbo':
            response = await openai.ChatCompletion.acreate(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
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
        response_txt = "Error (APIError).  Something went wrong on our side.  Please try again, and if it repeats, let me know at mliffito@iwu.edu."
        pass
    except openai.error.Timeout as e:
        current_app.logger.error(e)
        response = str(e)
        response_txt = "Error (Timeout).  Something went wrong on our side.  Please try again, and if it repeats, let me know at mliffito@iwu.edu."
        pass
    except openai.error.ServiceUnavailableError as e:
        current_app.logger.error(e)
        response = str(e)
        response_txt = "Error (ServiceUnavailableError).  Something went wrong on our side.  Please try again, and if it repeats, let me know at mliffito@iwu.edu."
        pass
    except openai.error.RateLimitError as e:
        current_app.logger.error(e)
        response = str(e)
        response_txt = "Error (RateLimitError).  The system is receiving too many requests right now.  Please try again in one minute.  If it does not resolve, please let me know at mliffito@iwu.edu."
        pass
    except Exception as e:
        current_app.logger.error(e)
        response = str(e)
        response_txt = "Error (Exception).  Something went wrong on our side.  Please try again, and if it repeats, let me know at mliffito@iwu.edu."
        pass

    return response, response_txt.strip()
