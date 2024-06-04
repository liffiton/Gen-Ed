# SPDX-FileCopyrightText: 2024 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

import asyncio
import datetime
import time
from collections.abc import Awaitable, Callable
from typing import Any

from openai.types.chat import ChatCompletionMessage
from openai.types.chat.chat_completion import ChatCompletion, Choice


def _create_dummy_completion() -> ChatCompletion:
    return ChatCompletion(
        id="fakeid",
        model="gpt-3.5-turbo",
        object="chat.completion",
        choices=[
            Choice(
                finish_reason="stop",
                index=0,
                message=ChatCompletionMessage(
                    content="x " * 500,
                    role="assistant",
                ),
            )
        ],
        created=int(datetime.datetime.now().timestamp()),
    )

def mock_completion(delay: float = 0.0) -> Callable[..., ChatCompletion]:
    def mock(*args: Any, **kwargs: Any) -> ChatCompletion:
        time.sleep(delay)
        return _create_dummy_completion()
    return mock


def mock_async_completion(delay: float = 0.0) -> Callable[..., Awaitable[ChatCompletion]]:
    async def mock(*args: Any, **kwargs: Any) -> ChatCompletion:
        await asyncio.sleep(delay)
        return _create_dummy_completion()
    return mock
