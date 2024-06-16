# SPDX-FileCopyrightText: 2024 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

import csv
import importlib
import inspect
import os
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI
from python_calamine import CalamineWorkbook


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


def load_prompt(app: str, csv_headers: list[str]) -> tuple[Callable[..., str | list[dict[str, str]]], Sequence[str]]:
    # Let the user choose a prompt function from the specified app
    prompts_module = importlib.import_module(f"{app}.prompts")
    prompt_functions = inspect.getmembers(prompts_module, inspect.isfunction)
    print("\x1B[33mChoose a prompt function:\x1B[m")
    for i, (name, func) in enumerate(prompt_functions):
        print(f" {i+1}: {name}")
    choice = int(input("Choice: "))
    prompt_func = prompt_functions[choice-1][1]

    # Get the required arguments / fields for the chosen prompt
    sig = inspect.signature(prompt_func)
    fields = [name for name in sig.parameters if sig.parameters[name].default == inspect.Parameter.empty]  # only args w/o default values for now

    # Check for headers in the given CSV matching the prompt's arguments
    missing = [field for field in fields if field not in csv_headers]
    if missing:
        print(f"\x1B[31mMissing columns in CSV needed for prompt:\x1B[m {missing}")
        sys.exit(1)

    return prompt_func, fields


def reload_prompt(app: str, func_name: str) -> Callable[..., str | list[dict[str, str]]]:
    prompt_module = importlib.import_module(f"{app}.prompts")
    importlib.reload(prompt_module)
    new_prompt_func = getattr(prompt_module, func_name)
    return new_prompt_func


def make_prompt(prompt_func, item):
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


def setup_openai() -> OpenAI:
    # load config values from .env file
    load_dotenv()
    try:
        openai_key = os.environ["OPENAI_API_KEY"]
    except KeyError:
        print("Error:  OPENAI_API_KEY environment variable not set.", file=sys.stderr)
        sys.exit(1)

    client = OpenAI(api_key=openai_key)
    return client
