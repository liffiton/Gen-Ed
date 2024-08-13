#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2023 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

import argparse
import itertools
from pathlib import Path

import litellm
import pyperclip
import urwid
from loaders import (
    get_available_prompts,
    load_prompt,
    load_queries,
    make_prompt,
    reload_prompt,
    test_and_report_model,
)

DEFAULT_MODEL = "gpt-3.5-turbo"
TEMPERATURE = 0.25
MAX_TOKENS = 1000


def msgs2str(messages: list[dict[str, str]]) -> str:
    return "\n".join(
        f"{msg['role']}: {msg['content']}" for msg in messages
    )


class QueryView(urwid.WidgetWrap):
    def __init__(self, model, prompt_func, queries, fields, footer_counter):
        self._model = model
        self._prompt_func = prompt_func
        self._queries = queries
        self._fields = fields
        self._footcnt = footer_counter
        self.curidx = 0
        self._contents = urwid.SimpleListWalker([])
        self._box = urwid.ListBox(self._contents)
        self.update()
        urwid.WidgetWrap.__init__(self, self._box)

    def set_prompt_func(self, new_func) -> None:
        self._prompt_func = new_func

    def update(self) -> None:
        self._footcnt.set_text(f"{self.curidx + 1} / {len(self._queries)}")
        item = self._queries[self.curidx]
        messages = make_prompt(self._prompt_func, item)
        item['__tester_prompt'] = messages

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
        ])
        new_contents.extend([
            urwid.Columns([
                (col_w, urwid.Text(('prompt_label', f"{msg['role']}: "), 'right')),
                urwid.Text(msg['content']),
            ])
            for msg in item.get('__tester_prompt', [])
        ])
        new_contents.extend([
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

    def next(self) -> None:
        if self.curidx == len(self._queries) - 1:
            return
        self.curidx += 1
        self.update()

    def prev(self) -> None:
        if self.curidx == 0:
            return
        self.curidx -= 1
        self.update()

    def copy_prompt(self) -> None:
        cur_prompt = self._queries[self.curidx]['__tester_prompt']
        prompt_str = msgs2str(cur_prompt)
        pyperclip.copy(prompt_str)

    def clear_response(self) -> None:
        item = self._queries[self.curidx]
        item['__tester_response'] = ""
        item['__tester_usage'] = ""

        self.update()

    def get_response(self) -> None:
        item = self._queries[self.curidx]
        messages = make_prompt(self._prompt_func, item)

        try:
            response = litellm.completion(
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


def main() -> None:
    # Setup / run config
    parser = argparse.ArgumentParser(description='A tool for running queries against data from a CSV/ODS/XLSX file.')
    parser.add_argument('app', type=str, help='The name of the application module from which to load prompts (e.g., codehelp or starburst).')
    parser.add_argument('file_path', type=Path, help='Path to the file to be read.')
    parser.add_argument(
        'model', type=str, nargs='?', default=DEFAULT_MODEL,
        help=f"(Optional. Default='{DEFAULT_MODEL}')  The LLM to use."
    )
    args = parser.parse_args()

    test_and_report_model(args.model)

    # Load data
    queries, headers = load_queries(args.file_path)

    # Initialize the prompt
    prompts = list(get_available_prompts(args.app).keys())
    print("\x1B[33mChoose a prompt function:\x1B[m")
    for i, name in enumerate(prompts):
       print(f" {i+1}: {name}")
    choice = int(input("Choice: "))
    prompt_name = prompts[choice-1]
    prompt_func, fields = load_prompt(args.app, prompt_name, headers)

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
    viewer = QueryView(args.model, prompt_func, queries, fields, footer_counter)
    frame = urwid.Frame(urwid.AttrMap(viewer, 'body'), header=header, footer=footer)

    palette = [
        ('header', 'black', 'light green'),
        ('footer', 'black', 'light cyan'),
        ('label', 'yellow', 'default'),
        ('prompt_label', 'light green', 'default'),
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
                viewer.clear_response()
                mainloop.draw_screen()
                viewer.get_response()
            case 'c':
                viewer.copy_prompt()
            case 'r':
                new_prompt_func = reload_prompt(args.app, prompt_func.__name__)  # get the new function using the old one's name
                viewer.set_prompt_func(new_prompt_func)
                viewer.update()
            case 'q':
                raise urwid.ExitMainLoop()

    # And go!
    mainloop = urwid.MainLoop(frame, palette, unhandled_input=unhandled)
    mainloop.run()


if __name__ == '__main__':
    main()
