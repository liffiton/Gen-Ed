import csv

from dotenv import load_dotenv
import openai
import urwid

import sys
import os
# small hack to import prompts from ..
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from codehelp import prompts  # noqa


def load_test_queries():
    with open("test_queries.csv") as csvfile:
        reader = csv.DictReader(csvfile)
        return list(reader)


class QueryView(urwid.WidgetWrap):
    def __init__(self, queries, footer_counter):
        self._queries = queries
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
        self._contents[:] = [
            urwid.Divider(),
            urwid.Columns([
                (col_w, urwid.Text(('label', "Code: "), 'right')),
                urwid.Text(item['code']),
            ]),
            urwid.Divider(),
            urwid.Columns([
                (col_w, urwid.Text(('label', "Error: "), 'right')),
                urwid.Text(item['error']),
            ]),
            urwid.Divider(),
            urwid.Columns([
                (col_w, urwid.Text(('label', "Issue: "), 'right')),
                urwid.Text(item['issue']),
            ]),
            urwid.Divider('-'),
            urwid.Columns([
                (col_w, urwid.Text(('response_label', "Response: "), 'right')),
                urwid.Text(item.get('response', '')),
            ]),
            urwid.Divider(),
        ]

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


def get_response(queries, index):
    item = queries[index]
    #prompt, stop_seq = prompts.make_main_prompt(
    prompt, stop_seq = prompts.make_sufficient_prompt(
        language="python",
        code=item['code'],
        error=item['error'],
        issue=item['issue'],
    )

    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
        #response = openai.Completion.create(
        #    model="text-davinci-003",
        #    prompt=prompt,
            temperature=0.25,
            max_tokens=1000,
            stop=stop_seq,
            # TODO: add user= parameter w/ unique ID of user (e.g., hash of username+email or similar)
        )

        response_txt = response.choices[0].message["content"]
        #response_txt = response.choices[0].text
        response_reason = response.choices[0].finish_reason  # e.g. "length" if max_tokens reached

        if response_reason == "length":
            response_txt += "\n\n[error: maximum length exceeded]"

        item['response'] = response_txt

    except:  # noqa
        item['response'] = "[An error occurred in the openai completion.]"


def main():
    # load config values from .env file
    load_dotenv()
    try:
        openai_key = os.environ["OPENAI_API_KEY"]
        openai.api_key = openai_key
    except KeyError:
        print("Error:  OPENAI_API_KEY environment variable not set.", file=sys.stderr)
        sys.exit(1)

    queries = load_test_queries()

    header = urwid.AttrMap(urwid.Text("Query Tester"), 'header')
    footer_counter = urwid.Text("x/x")
    footer = urwid.AttrMap(
        urwid.Columns([
            (15, urwid.Text("Query Tester")),
            (10, footer_counter),
            urwid.Text("j:next, k:prev, g:get response, q:quit", 'right'),
        ]),
        'footer'
    )
    viewer = QueryView(queries, footer_counter)
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
                get_response(queries, viewer.curidx)
                viewer.update()
            case 'q':
                raise urwid.ExitMainLoop()

    urwid.MainLoop(frame, palette, unhandled_input=unhandled).run()


if __name__ == '__main__':
    main()
