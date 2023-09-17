#!/usr/bin/env python3

import argparse
import csv
import itertools

from dotenv import load_dotenv
import openai
import pyperclip
import urwid

from inspect import Parameter
import importlib
import inspect
import sys
import os


TEMPERATURE = 0.5
MAX_TOKENS = 1000


def msgs2str(messages):
    return "\n".join(
        f"{msg['role']}: {msg['content']}" for msg in messages
    )


def load_queries(filename):
    with open(filename) as csvfile:
        reader = csv.DictReader(csvfile)
        return list(reader), reader.fieldnames


def load_prompt(app, csv_headers):
    # Let the user choose a prompt function from the specified app
    prompts_module = importlib.import_module(f"{app}.prompts")
    prompt_functions = inspect.getmembers(prompts_module, inspect.isfunction)
    print("[33mChoose a prompt function:[m")
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
        print(f"[31mMissing columns in CSV needed for prompt:[m {missing}")
        sys.exit(1)

    return prompt_func, fields


class QueryView(urwid.WidgetWrap):
    def __init__(self, queries, fields, footer_counter):
        self._queries = queries
        self._fields = fields
        self._footcnt = footer_counter
        self.curidx = 0
        self._contents = urwid.SimpleListWalker([])
        self._box = urwid.ListBox(self._contents)
        self.update()
        urwid.WidgetWrap.__init__(self, self._box)

    def update(self):
        self._footcnt.set_text(f"{self.curidx + 1} / {len(self._queries)}")
        item = self._queries[self.curidx]
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


def get_prompt(item, prompt_func):
    # Call the prompt function with arguments from the current item
    args = [item[name] for name in inspect.signature(prompt_func).parameters if name in item]
    prompt_gen = prompt_func(*args)

    if isinstance(prompt_gen, list):
        # The prompt function outputs in the chat completion format, not a string,
        # and the davinci model does not handle chat completions.
        prompt = None
        messages = prompt_gen
    else:
        prompt = prompt_gen
        messages = [{"role": "user", "content": prompt}]

    return prompt, messages


def get_response(item, prompt, messages, model):
    '''
    model can be either 'text-davinci-003' or 'gpt-{4, 3.5-turbo, etc.}'
    '''
    try:
        if model.startswith("text-davinci"):
            assert (prompt is not None), "Invalid prompt function for using with text-davinci (outputs messages for a chat completion only)."
            response = openai.Completion.create(
                model=model,
                prompt=prompt,
                temperature=TEMPERATURE,
                max_tokens=MAX_TOKENS,
            )
            response_txt = response.choices[0].text
        elif model.startswith("gpt-"):
            response = openai.ChatCompletion.create(
                model=model,
                messages=messages,
                temperature=TEMPERATURE,
                max_tokens=MAX_TOKENS,
                n=2,
            )
            response_txt = '\n\n----------\n\n'.join(x.message['content'] for x in response.choices)
        else:
            raise Exception(f"Invalid model specified: {model}")

        response_reason = response.choices[-1].finish_reason  # e.g. "length" if max_tokens reached

        if response_reason == "length":
            response_txt += "\n\n[error: maximum length exceeded]"

        item['__tester_response'] = response_txt

        item['__tester_usage'] = f"Prompt: {response.usage['prompt_tokens']}  Completion: {response.usage['completion_tokens']}  Total: {response.usage['total_tokens']}"

    except Exception as e:  # noqa
        item['__tester_response'] = f"[An error occurred in the openai completion.]\n{e}"


def setup_openai():
    # load config values from .env file
    load_dotenv()
    try:
        openai_key = os.environ["OPENAI_API_KEY"]
        openai.api_key = openai_key
    except KeyError:
        print("Error:  OPENAI_API_KEY environment variable not set.", file=sys.stderr)
        sys.exit(1)


def main():
    setup_openai()

    # Setup / run config
    parser = argparse.ArgumentParser(description='A tool for running queries against data from a CSV file.')
    parser.add_argument('filename', type=str, help='The filename of the CSV file to be read.')
    parser.add_argument('app', type=str, help='The name of the application module from which to load prompts (e.g., codehelp or starburst).')
    parser.add_argument(
        'model', type=str, nargs='?', default='gpt-3.5-turbo',
        help='(Optional. Default="gpt-3.5-turbo")  The LLM to use (text-davinci-003 or gpt-{3.5-turbo, 4, etc.}).'
    )
    args = parser.parse_args()

    # Load data
    queries, csv_headers = load_queries(args.filename)

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
    viewer = QueryView(queries, fields, footer_counter)
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
        nonlocal prompt_func  # to allow modifying prompt_func
        match key:
            case 'j':
                viewer.next()
            case 'k':
                viewer.prev()
            case 'g':
                item = queries[viewer.curidx]
                prompt, messages = get_prompt(item, prompt_func)
                item['__tester_prompt'] = prompt if args.model.startswith('text-davinci') else msgs2str(messages)
                viewer.update()
                mainloop.draw_screen()
                get_response(item, prompt, messages, args.model)
                viewer.update()
            case 'c':
                viewer.copy_prompt()
            case 'r':
                prompt_module = importlib.import_module(f"{args.app}.prompts")
                importlib.reload(prompt_module)
                prompt_func = getattr(prompt_module, prompt_func.__name__)  # get the new function using the old one's name
            case 'q':
                raise urwid.ExitMainLoop()

    # And go!
    mainloop = urwid.MainLoop(frame, palette, unhandled_input=unhandled)
    mainloop.run()


if __name__ == '__main__':
    main()
