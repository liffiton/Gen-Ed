# SPDX-FileCopyrightText: 2024 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

import csv
import importlib
import inspect
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

import litellm
from python_calamine import CalamineWorkbook


def test_and_report_model(model: str) -> None:
    # Check for valid model
    response = litellm.completion(
        model=model,
        messages=[{"role": "user", "content": "Write \"OK.\""}],
        max_tokens=3,
    )
    assert response.choices[0].message.content.strip() == "OK."
    print(f"Using model: \x1B[32m{model}\x1B[m")


def load_queries(file_path: Path) -> tuple[list[dict[str, Any]], Sequence[str]]:
    """ Load query data from a spreadsheet (.csv, .ods, or .xlsx).
    Assumes the first row contains column headers.
    """
    if file_path.suffix == ".csv":
        with file_path.open() as csvfile:
            reader = csv.DictReader(csvfile)
            assert reader.fieldnames is not None
            return list(reader), reader.fieldnames
    else:
        # assume .ods or .xlsx
        book = CalamineWorkbook.from_path(file_path)
        # assume we want the first sheet
        sheet = book.get_sheet_by_index(0).to_python()
        fieldnames = [str(x) for x in sheet[0]]
        rows = [{name: row[i] for i, name in enumerate(fieldnames)} for row in sheet[1:]]
        return rows, fieldnames


def get_available_prompts(app: str) -> dict[str, Callable[..., str | list[dict[str, str]]]]:
    prompts_module = importlib.import_module(f"{app}.prompts")
    prompt_functions = inspect.getmembers(prompts_module, inspect.isfunction)
    return {name: func for name, func in prompt_functions}


def load_prompt(app: str, prompt_func_name: str, csv_headers: Sequence[str]) -> tuple[Callable[..., str | list[dict[str, str]]], Sequence[str]]:
    available_prompts = get_available_prompts(app)
    prompt_func = available_prompts[prompt_func_name]

    params = inspect.signature(prompt_func).parameters
    fields = list(params.keys())
    required_fields = [f for f in params if params[f].default == inspect.Parameter.empty]

    # Check for headers in the given CSV matching the prompt's required arguments
    missing = [field for field in required_fields if field not in csv_headers]
    if missing:
        raise ValueError(f"Missing columns in CSV needed for prompt: {missing}")

    return prompt_func, fields


def reload_prompt(app: str, func_name: str) -> Callable[..., str | list[dict[str, str]]]:
    prompt_module = importlib.import_module(f"{app}.prompts")
    importlib.reload(prompt_module)
    new_prompt_func = getattr(prompt_module, func_name)
    return new_prompt_func  # type: ignore


def make_prompt(prompt_func: Callable[..., str | list[dict[str, str]]], item: dict[str, Any]) -> list[dict[str, str]]:
    # Call the prompt function with arguments from the given item
    args = [item[name] for name in inspect.signature(prompt_func).parameters if name in item]
    prompt_gen = prompt_func(*args)

    if isinstance(prompt_gen, list):
        # The prompt function outputs in the chat completion format.
        messages = prompt_gen
    else:
        # The prompt function outputs a string.
        messages = [{"role": "user", "content": prompt_gen}]

    return messages
