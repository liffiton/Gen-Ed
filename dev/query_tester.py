import argparse
import csv
from importlib import reload
import itertools

from dotenv import load_dotenv
import openai
import pyperclip
import urwid

import sys
import os
# small hack to import prompts from ..
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from codehelp import prompts  # noqa


def msgs2str(messages):
    return "\n".join(
        f"{msg['role']}: {msg['content']}" for msg in messages
    )


def load_queries(filename):
    with open(filename) as csvfile:
        reader = csv.DictReader(csvfile)
        return list(reader)


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
        col_w = 10
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


def get_response(queries, index, test_type, model):
    '''
    model can be either 'davinci' or 'turbo'
    '''
    item = queries[index]

    match test_type:
        case "helper":
            prompt = prompts.make_main_prompt(
                language="python",
                code=item['code'],
                error=item['error'],
                issue=item['issue'],
            )
            messages = [{"role": "user", "content": prompt}]
        case "sufficient":
            prompt = prompts.make_sufficient_prompt(
                language="python",
                code=item['code'],
                error=item['error'],
                issue=item['issue'],
            )
            messages = [{"role": "user", "content": prompt}]
        case "cleanup":
            prompt = prompts.make_cleanup_prompt(item['response_text'])
            messages = [{"role": "user", "content": prompt}]
        case "topics":
            assert model != "davinci"
            messages = prompts.make_topics_prompt(
                language="python",
                code=item['code'],
                error=item['error'],
                issue=item['issue'],
                response=item['response_text']
            )

    try:
        if model == 'davinci':
            item['__tester_prompt'] = prompt
            response = openai.Completion.create(
                model="text-davinci-003",
                prompt=prompt,
                temperature=0.25,
                max_tokens=1000,
            )
            response_txt = response.choices[0].text
        elif model == 'turbo':
            item['__tester_prompt'] = msgs2str(messages)
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=messages,
                temperature=0.25,
                max_tokens=1000,
                n=3,
            )
            response_txt = '\n\n----------\n\n'.join(x.message['content'] for x in response.choices)

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
    parser.add_argument('test_type', type=str, choices=['helper', 'sufficient', 'cleanup', 'topics'], help='The type of test to run.')
    parser.add_argument('model', type=str, choices=['davinci', 'turbo'], help='The LLM to use.')
    args = parser.parse_args()

    queries = load_queries(args.filename)

    match args.test_type:
        case "helper" | "sufficient":
            fields = ['code', 'error', 'issue']
        case "cleanup":
            fields = ['response_text']
        case "topics":
            fields = ['code', 'error', 'issue', 'response_text']

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

    def unhandled(key):
        match key:
            case 'j':
                viewer.next()
            case 'k':
                viewer.prev()
            case 'g':
                get_response(queries, viewer.curidx, args.test_type, args.model)
                viewer.update()
            case 'c':
                viewer.copy_prompt()
            case 'r':
                reload(prompts)
            case 'q':
                raise urwid.ExitMainLoop()

    # And go!
    urwid.MainLoop(frame, palette, unhandled_input=unhandled).run()


if __name__ == '__main__':
    main()
