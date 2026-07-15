# SPDX-FileCopyrightText: 2026 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

from typing import Any, Literal, Self, TypeAlias, TypedDict, cast

import msgspec
from werkzeug.datastructures import ImmutableMultiDict

from gened.class_config.types import ConfigItem
from gened.llm import ChatMessage

ChatMode: TypeAlias = Literal["inquiry", "guided"]
ObjectiveStatus: TypeAlias = Literal["not started", "moved on", "in progress", "completed"]


class ObjectivesResponse(msgspec.Struct):
    """LLM response for objective generation."""
    objectives: list[str]


class QuestionsResponse(msgspec.Struct):
    """LLM response for question generation."""
    questions: list[str]


class ContextDocument(msgspec.Struct, kw_only=True):
    filename: str
    text: str
    use_in: set[Literal["setup", "chat"]] = set()


class LearningObjective(msgspec.Struct):
    name: str
    questions: list[str] = []


class TutorConfig(ConfigItem):
    topic: str = ""
    context: str = ""
    documents: list[ContextDocument] = []     # noqa: RUF012 - ConfigItem is a msgspec.Struct, so this is okay
    objectives: list[LearningObjective] = []  # noqa: RUF012 - ConfigItem is a msgspec.Struct, so this is okay
    opening_message: str = ""

    @classmethod
    def from_request_form(cls, form: ImmutableMultiDict[str, Any]) -> Self:
        """
        Populates a TutorConfig from the given form.
        """
        config = cls.initial()
        if 'row_id' in form:
            config.row_id = int(form['row_id'])
        config.name = form.get('name', '').strip()
        config.topic = form.get('topic', '').strip()
        config.context = form.get('context', '').strip()
        config.opening_message = form.get('opening_message', '').strip()
        # Parse documents from array-style form fields
        filenames = form.getlist('document_filename[]')
        texts = form.getlist('document_text[]')
        use_ins = form.getlist('document_use_in[]')

        # Build documents list, filtering out empty ones
        documents = []
        for fn_raw, txt_raw, use_in_str in zip(filenames, texts, use_ins, strict=True):
            fn = fn_raw.strip()
            txt = txt_raw.strip()
            if not txt:
                continue

            # Parse use_in - it comes as comma-separated string from form
            if use_in_str:
                use_in_list = [u.strip() for u in use_in_str.split(',') if u.strip()]
            else:
                use_in_list = ['setup']  # default
            # Validate correct literals - we control the input values via the form
            assert all(u in ('setup', 'chat') for u in use_in_list), f"Invalid use_in values: {use_in_list}"
            documents.append(ContextDocument(filename=fn, text=txt, use_in=set(use_in_list)))

        config.documents = documents

        objective_names = form.getlist('objectives')
        config.objectives = [LearningObjective(obj, form.getlist(f'questions[{i}]')) for i, obj in enumerate(objective_names)]
        return config


class GuidedObjectiveProgress(msgspec.Struct):
    """Progress on a single learning objective."""
    objective: str
    status: ObjectiveStatus


class GuidedAnalysis(msgspec.Struct):
    """Analysis of a guided tutor chat."""
    summary: str
    progress: list[GuidedObjectiveProgress]


# We use this in place of ChatMessage (an alias for
# openai.types.chat.ChatCompletionMessageParam), because msgspec won't decode
# into a union of typeddicts (which is what ChatMessage is), but it will into
# this.  And this encodes all of the type constraints we actually need, anyway.
class ChatMessageX(TypedDict):
    role: Literal["system", "assistant", "user"]
    content: str


class ChatData(msgspec.Struct, kw_only=True, omit_defaults=True):
    topic: str
    messages: list[ChatMessageX]
    mode: ChatMode
    id: int | None = None
    user_id: int | None = None
    user_json: str | None = None
    class_id: int | None = None
    context_name: str | None = None
    usages: list[dict[str, int | dict[str, int]]] = []
    analysis: GuidedAnalysis | None = None

    # We have to cast to list[ChatMessage] before passing these into OpenAI API
    # functions, because MyPy can't tell our custom ChatMessageX is a valid
    # substitute.
    @property
    def openai_messages(self) -> list[ChatMessage]:
        return cast("list[ChatMessage]", self.messages)
