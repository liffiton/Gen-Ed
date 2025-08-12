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

    def _translate_openai_error(self, e: openai.APIError) -> tuple[str, str]:
        common_error_text = "Error ({error_type}).  Something went wrong with this query.  The error has been logged, and we'll work on it.  For now, please try again."
        match e:
            case openai.APITimeoutError():
                user_msg = "Error (APITimeoutError).  The system timed out producing the response.  Please try again."
                log_msg = f"OpenAI Timeout: {e}"
            case openai.RateLimitError():
                if "exceeded your current quota" in str(e):
                    user_msg = "Error (RateLimitError).  The API key for this class has exceeded its current quota (https://platform.openai.com/docs/guides/rate-limits/usage-tiers).  The instructor should check their API plan and billing details.  Possibly the key is in the free tier, which does not cover the models used here."
                else:
                    user_msg = "Error (RateLimitError).  The system is receiving too many requests right now.  Please try again in one minute."
                log_msg = f"OpenAI RateLimitError: {e}"
            case openai.AuthenticationError():
                user_msg = "Error (AuthenticationError).  The API key set by the instructor for this class is invalid.  A valid API key is needed for this application to work."
                log_msg = f"OpenAI AuthenticationError: {e}"
            case openai.BadRequestError():
                if "API key not valid" in str(e):
                    user_msg = "Error (BadRequestError).  The API key set by the instructor for this class is invalid.  A valid API key is needed for this application to work."
                elif "maximum context length" in str(e):
                    user_msg = "Error (BadRequestError).  Your query is too long for the model to process.  Please reduce the length of your input."
                else:
                    user_msg = common_error_text.format(error_type='BadRequestError')
                log_msg = f"OpenAI BadRequestError: {e}"
            case _:
                user_msg = common_error_text.format(error_type='APIError')
                log_msg = f"Exception (OpenAI {type(e).__name__}, but I don't handle that specifically yet): {e}"

        return user_msg, log_msg

    async def get_completion(self, messages: list[OpenAIChatMessage], extra_args: dict[str, Any] | None = None) -> tuple[dict[str, str], str]:
        """Get a completion from the LLM.

        Args:
            messages: A list of chat messages in OpenAI format
            extra_args: A dictionary of additional named arguments to pass to the API

        Returns:
            A tuple containing:
            - The raw API response as a dict
            - The response text (stripped)

        Note:
            If an error occurs, the dict will contain an 'error' key with the error details,
            and the text will contain a user-friendly error message.
        """
        completion_args: dict[str, Any] = {
            'temperature': 0.25,
            'max_tokens': 2000,
        }
        if extra_args:
            completion_args |= extra_args

        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                **completion_args
            )

        except openai.APIError as e:
            user_msg, log_msg = self._translate_openai_error(e)
            current_app.logger.error(log_msg)
            return {'error': str(e)}, user_msg

        else:
            choice = response.choices[0]
            response_txt = choice.message.content or ""

            if choice.finish_reason == "length":  # "length" if max_tokens reached
                response_txt += "\n\n[error: maximum length exceeded]"

            return response.model_dump(), response_txt.strip()
