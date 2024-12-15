from typing import Any, TypeAlias

import openai
from flask import current_app

OpenAIChatMessage: TypeAlias = openai.types.chat.ChatCompletionMessageParam


class OpenAIClient:
    """Client for interacting with OpenAI or compatible API endpoints."""

    def __init__(self, model: str, api_key: str, *, base_url: str | None = None):
        """Initialize an OpenAI client.

        Args:
            model: The model identifier to use for completions
            api_key: The API key for authentication
            base_url: Optional base URL for non-OpenAI providers
        """
        if base_url:
            self._client = openai.AsyncOpenAI(api_key=api_key, base_url=base_url)
        else:
            self._client = openai.AsyncOpenAI(api_key=api_key)
        self._model = model

    async def get_completion(self, prompt: str | None = None, messages: list[OpenAIChatMessage] | None = None, extra_args: dict[str, Any] | None = None) -> tuple[dict[str, str], str]:
        """Get a completion from the LLM.

        Args:
            prompt: A single prompt string (converted to a message if provided)
            messages: A list of chat messages in OpenAI format
            (Only one of prompt or messages should be provided)

        Returns:
            A tuple containing:
            - The raw API response as a dict
            - The response text (stripped)

        Note:
            If an error occurs, the dict will contain an 'error' key with the error details,
            and the text will contain a user-friendly error message.
        """
        common_error_text = "Error ({error_type}).  Something went wrong with this query.  The error has been logged, and we'll work on it.  For now, please try again."
        completion_args: dict[str, Any] = {
            'temperature': 0.25,
            'max_tokens': 1000,
        }
        if extra_args:
            completion_args |= extra_args

        try:
            if messages is None:
                assert prompt is not None
                messages = [{"role": "user", "content": prompt}]

            response = await self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                **completion_args
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

