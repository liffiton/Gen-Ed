# SPDX-FileCopyrightText: 2023 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

from collections.abc import Iterable

from jinja2 import Environment
from openai.types.chat import ChatCompletionMessageParam

jinja_env = Environment(
    trim_blocks=True,
    lstrip_blocks=True,
)

common_template_sys1 = jinja_env.from_string("""\
You are a system for assisting students learning CS and programming.  Your job here is {{ job }}.

A query contains:
 - the programming language (in "<lang>" delimiters)
{% if code %}
 - a relevant snippet of their code (in "<code>")
{% endif %}
{% if error %}
 - an error message they are seeing (in "<error>")
{% endif %}
{% if issue or not error %}
 - an issue or question and how they want assistance (in "<issue>")
{% endif %}
""")

common_template_user = jinja_env.from_string("""\
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
""")

main_template_sys2 = jinja_env.from_string("""\
If the student query is off-topic, respond with an error.

Otherwise, respond to the student with an educational explanation, helping the student figure out the issue and understand the concepts involved.  If the student query includes an error message, tell the student what it means, giving a detailed explanation to help the student understand the message.  Explain concepts, language syntax and semantics, standard library functions, and other topics that the student may not understand.  Be positive and encouraging!

- Do not write a corrected or updated version of the student's code.  You must not write code for the student.
{% if avoid_set %}
- Do not use in your response:
{% for avoid_item in avoid_set %}
  - {{ avoid_item }}
{% endfor %}
{% endif %}
- Use Markdown formatting, including ` for inline code.
- Do not write a heading for the response.
- Do not write any example code blocks.
- If the student wrote in a language other than English, always respond in the student's own language.

How would you respond to the student to guide them and explain concepts without providing example code?
""")


def make_main_prompt(language: str, code: str, error: str, issue: str, avoid_set: Iterable[str] | None = None) -> list[ChatCompletionMessageParam]:
    error = error.rstrip()
    issue = issue.rstrip()
    if error and not issue:
        issue = "Please help me understand this error."

    sys_job = "to respond to a student's query as a helpful expert teacher"
    return [
        {'role': 'system', 'content': common_template_sys1.render(job=sys_job, language=language, code=code, error=error, issue=issue)},
        {'role': 'user',   'content': common_template_user.render(language=language, code=code, error=error, issue=issue)},
        {'role': 'system', 'content': main_template_sys2.render(avoid_set=avoid_set)},
    ]


sufficient_template_sys2 = jinja_env.from_string("""\
Do not tell the student how to solve the issue or correct the code.  Instead, please assess their query and tell them whether it is sufficient for you to potentially provide help (write "OK.") or not (ask for clarification).
 - If the query is sufficient and you might be able to help, say "OK."
 - Or, if the query is missing important information required for you to help, write directly to the student and clearly describe the additional information you need.  Ask for the most important pieces of information first, and do not overwhelm the student with too many requests.
""")


def make_sufficient_prompt(language: str, code: str, error: str, issue: str) -> list[ChatCompletionMessageParam]:
    error = error.rstrip()
    issue = issue.rstrip()
    if error and not issue:
        issue = "Please help me understand this error."

    sys_job = "to evaluate whether a student's query is sufficient for you to provide effective assistance"
    return [
        {'role': 'system', 'content': common_template_sys1.render(job=sys_job, language=language, code=code, error=error, issue=issue)},
        {'role': 'user',   'content': common_template_user.render(language=language, code=code, error=error, issue=issue)},
        {'role': 'system', 'content': sufficient_template_sys2.render(language=language, code=code, error=error, issue=issue)},
    ]


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
        {'role': 'system', 'content': "Respond with a JSON-formatted array of strings with NO other text, like: [\"Item1\",\"Item2\",\"Item3\",\"Item4\"]"}
    ]

    return messages
