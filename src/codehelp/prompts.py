# SPDX-FileCopyrightText: 2023 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

import random
from collections.abc import Iterable

from jinja2 import Environment
from openai.types.chat import ChatCompletionMessageParam

jinja_env = Environment(
    trim_blocks=True,
    lstrip_blocks=True,
)


def make_main_prompt(language: str, code: str, error: str, issue: str, avoid_set: Iterable[str] | None = None) -> str:
    # generate the extra / avoidance instructions
    if avoid_set is not None:
        extra_text = f"Do not use in your response: {', '.join(avoid_set)}."
    else:
        extra_text = ""

    error = error.rstrip()
    issue = issue.rstrip()
    if error and not issue:
        issue = "Please help me understand this error."
    elif not error:
        error = "[no error message]"

    nonce = random.randint(1000, 9999)
    return f"""You are a system for assisting students learning CS and programming.
The students provide:
 1) the programming language (in "<lang>" delimiters)
 2) a relevant snippet of their code (in "<code_{nonce}>")
 3) an error message they are seeing (in "<error_{nonce}>")
 4) their issue or question and how they want assistance (in "<issue_{nonce}>")

<lang>{language}</lang>
<code_{nonce}>
{code}
</code_{nonce}>
<error_{nonce}>
{error}
</error_{nonce}>
<issue_{nonce}>
{issue}
</issue_{nonce}>

If the student input is off-topic, respond with an error.

Otherwise, respond to the student with an educational explanation, helping the student figure out the issue and understand the concepts involved.  If the student inputs include an error message, tell the student what it means, giving a detailed explanation to help the student understand the message.  Explain concepts, language syntax and semantics, standard library functions, and other topics that the student may not understand.  Be positive and encouraging!

Do not write a corrected or updated version of the student's code.  You must not write code for the student.

{extra_text}

- Use Markdown formatting, including ` for inline code.
- Do not write a heading for the response.
- Do not write any example code blocks.

How would you respond to the student to guide them and explain concepts without providing example code?
"""


sufficient_template = jinja_env.from_string("""\
You are a system for assisting students learning CS and programming.

I provide:
 - the programming language (in "<lang>" delimiters)
{% if code %}
 - a relevant snippet of my code (in "<code>")
{% endif %}
{% if error %}
 - an error message I am seeing (in "<error>")
{% endif %}
{% if issue or not error %}
 - my issue or question and how I want assistance (in "<issue>")
{% endif %}

Here is my submission:

<lang>
{{language if language != 'C' else 'the C language'}}
</lang>
{% if code %}
<code>
{{code}}
</code>
{% endif %}
{% if error %}
<error>
{{error}}
</error>
{% endif %}
{% if issue or not error %}
<issue>
{{issue}}
</issue>
{% endif %}

Do not tell me how to solve or correct anything.  Instead, please assess my submission and tell me whether it is sufficient for you to potentially provide help (write "OK.") or if you cannot help without additional information.
 - If important information required for you to help is missing, tell me what additional information you need.
 - Or, if the submission is sufficient and you might be able to help, write "OK."
""")


def make_sufficient_prompt(language: str, code: str, error: str, issue: str) -> str:
    error = error.rstrip()
    issue = issue.rstrip()
    if error and not issue:
        issue = "Please help me understand this error."
    return sufficient_template.render(language=language, code=code, error=error, issue=issue)


def make_cleanup_prompt(response_text: str) -> str:
    return f"""The following was written to help a student in a CS class.  However, any example code (such as in ``` Markdown delimiters) can give the student an assignment's answer rather than help them figure it out themselves.  We need to provide help without including example code.  To do this, rewrite the following to remove any code blocks so that the response explains what the student should do but does not provide solution code.
---
{response_text}
---
Rewritten:
"""


def make_topics_prompt(language: str, code: str, error: str, issue: str, response_text: str) -> list[ChatCompletionMessageParam]:
    messages : list[ChatCompletionMessageParam] = [
        {'role': 'user', 'content': f"""\
<language>{language}</language>
<code>{code}</code>
<error>{error}</error>
<issue>{issue}</issue>
"""},
        {'role': 'assistant', 'content': response_text},
        {'role': 'user', 'content': "Please give me a list of specific concepts I appear to be having difficulty with in the above exchange.  Write each in title case."},
        {'role': 'assistant', 'content': "[inner monologue] I need to respond with a JSON-formatted array of strings with NO other text, like: ['Item1','Item2','Item3','Item4']"}
    ]

    return messages
