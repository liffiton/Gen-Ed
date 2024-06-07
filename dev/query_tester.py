#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2023 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

import argparse
import csv
import importlib
import inspect
import itertools
import os
import sys
from inspect import Parameter
from pathlib import Path

import pyperclip
import urwid
from dotenv import load_dotenv
from openai import OpenAI

TEMPERATURE = 0.25
MAX_TOKENS = 1000


def msgs2str(messages):
    return "\n".join(
        f"{msg['role']}: {msg['content']}" for msg in messages
    )


def load_queries(csv_path):
    with csv_path.open() as csvfile:
        reader = csv.DictReader(csvfile)
        return list(reader), reader.fieldnames


def load_prompt(app, csv_headers):
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
    fields = [name for name in sig.parameters if sig.parameters[name].default == Parameter.empty]  # only args w/o default values for now

    # Check for headers in the given CSV matching the prompt's arguments
    missing = [field for field in fields if field not in csv_headers]
    if missing:
        print(f"\x1B[31mMissing columns in CSV needed for prompt:\x1B[m {missing}")
        sys.exit(1)

    return prompt_func, fields


class QueryView(urwid.WidgetWrap):
    def __init__(self, client, model, prompt_func, queries, fields, footer_counter):
        self._client = client
        self._model = model
        if not model.startswith("gpt-"):
            raise Exception(f"Invalid model specified: {model}")

        self._prompt_func = prompt_func
        self._queries = queries
        self._fields = fields
        self._footcnt = footer_counter
        self.curidx = 0
        self._contents = urwid.SimpleListWalker([])
        self._box = urwid.ListBox(self._contents)
        self.update()
        urwid.WidgetWrap.__init__(self, self._box)

    def _get_prompt(self, item):
        # Call the prompt function with arguments from the current item
        args = [item[name] for name in inspect.signature(self._prompt_func).parameters if name in item]
        prompt_gen = self._prompt_func(*args)

        if isinstance(prompt_gen, list):
            # The prompt function outputs in the chat completion format.
            messages = prompt_gen
        else:
            # The prompt function outputs a string.
            messages = [{"role": "user", "content": prompt_gen}]

        return messages

    def set_prompt_func(self, new_func):
        self._prompt_func = new_func

    def update(self):
        self._footcnt.set_text(f"{self.curidx + 1} / {len(self._queries)}")
        item = self._queries[self.curidx]
        messages = self._get_prompt(item)
        item['__tester_prompt'] = msgs2str(messages)

        col_w = 15
        new_contents = list(itertools.chain.from_iterable(
            (
                urwid.Divider(),
                urwid.Columns([
                    (col_w, urwid.Text(('label', f"{field}: "), 'right')),
                    urwid.Text(item[field]),
                ])
            )
            for field in self._fields
        ))
        new_contents.extend([
            urwid.Divider('-'),
            urwid.Columns([
                (col_w, urwid.Text(('label', "Prompt: "), 'right')),
                urwid.Text(item.get('__tester_prompt', '')),
            ]),
            urwid.Divider('-'),
            urwid.Columns([
                (col_w, urwid.Text(('response_label', "Usage: "), 'right')),
                urwid.Text(item.get('__tester_usage', '')),
            ]),
            urwid.Divider(),
            urwid.Columns([
                (col_w, urwid.Text(('response_label', "Response: "), 'right')),
                urwid.Text(item.get('__tester_response', '')),
            ]),
            urwid.Divider(),
        ])

        self._contents[:] = new_contents

    def next(self):
        if self.curidx == len(self._queries) - 1:
            return
        self.curidx += 1
        self.update()

    def prev(self):
        if self.curidx == 0:
            return
        self.curidx -= 1
        self.update()

    def copy_prompt(self):
        cur_prompt = self._queries[self.curidx]['__tester_prompt']
        pyperclip.copy(cur_prompt)

    def get_response(self):
        item = self._queries[self.curidx]
        messages = self._get_prompt(item)

        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                temperature=TEMPERATURE,
                max_tokens=MAX_TOKENS,
                n=1,
            )
        except Exception as e:  # noqa
            item['__tester_response'] = f"[An error occurred in the openai completion.]\n{e}"
            return

        response_txt = '\n\n----------\n\n'.join(x.message.content for x in response.choices)
        response_reason = response.choices[-1].finish_reason  # e.g. "length" if max_tokens reached

        if response_reason == "length":
            response_txt += "\n\n[error: maximum length exceeded]"

        item['__tester_response'] = response_txt

        item['__tester_usage'] = f"Prompt: {response.usage.prompt_tokens}  Completion: {response.usage.completion_tokens}  Total: {response.usage.total_tokens}"

        self.update()


def setup_openai():
    # load config values from .env file
    load_dotenv()
    try:
        openai_key = os.environ["OPENAI_API_KEY"]
    except KeyError:
        print("Error:  OPENAI_API_KEY environment variable not set.", file=sys.stderr)
        sys.exit(1)

    client = OpenAI(api_key=openai_key)
    return client


def main():
    # Setup / run config
    parser = argparse.ArgumentParser(description='A tool for running queries against data from a CSV file.')
    parser.add_argument('csv_path', type=Path, help='The filename of the CSV file to be read.')
    parser.add_argument('app', type=str, help='The name of the application module from which to load prompts (e.g., codehelp or starburst).')
    parser.add_argument(
        'model', type=str, nargs='?', default='gpt-3.5-turbo',
        help='(Optional. Default="gpt-3.5-turbo")  The LLM to use (gpt-{3.5-turbo, 4o, etc.}).'
    )
    args = parser.parse_args()

    # Get an OpenAI client object
    client = setup_openai()

    # Load data
    queries, csv_headers = load_queries(args.csv_path)

    # Initialize the prompt
    prompt_func, fields = load_prompt(args.app, csv_headers)

    # Make the UI
    header = urwid.AttrMap(urwid.Text("Query Tester"), 'header')
    footer_counter = urwid.Text("x/x")
    footer = urwid.AttrMap(
        urwid.Columns([
            (15, urwid.Text("Query Tester")),
            (10, footer_counter),
            urwid.Text("j:next, k:prev, g:get response, c:copy prompt, r:reload prompts, q:quit", 'right'),
        ]),
        'footer'
    )
    viewer = QueryView(client, args.model, prompt_func, queries, fields, footer_counter)
    frame = urwid.Frame(urwid.AttrMap(viewer, 'body'), header=header, footer=footer)

    palette = [
        ('header', 'black', 'light green'),
        ('footer', 'black', 'light cyan'),
        ('label', 'yellow', 'default'),
        ('response_label', 'light red', 'default'),
    ]

    # variable for unhandled to get a reference to it; set later when mainloop is created (which requires unhandled be defined first)
    mainloop = None

    def unhandled(key):
        match key:
            case 'j':
                viewer.next()
            case 'k':
                viewer.prev()
            case 'g':
                viewer.get_response()
            case 'c':
                viewer.copy_prompt()
            case 'r':
                prompt_module = importlib.import_module(f"{args.app}.prompts")
                importlib.reload(prompt_module)
                new_prompt_func = getattr(prompt_module, prompt_func.__name__)  # get the new function using the old one's name
                viewer.set_prompt_func(new_prompt_func)
                viewer.update()
            case 'q':
                raise urwid.ExitMainLoop()

    # And go!
    mainloop = urwid.MainLoop(frame, palette, unhandled_input=unhandled)
    mainloop.run()


if __name__ == '__main__':
    main()
