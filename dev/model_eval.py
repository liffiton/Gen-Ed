#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2024 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

import argparse
import json
import sqlite3
import sys
import time
from pathlib import Path
from sqlite3 import Row

import litellm
from loaders import (
    get_available_prompts,
    load_prompt,
    load_queries,
    make_prompt,
    test_and_report_model,
)
from tqdm.auto import tqdm

DEFAULT_MODEL = "anthropic/claude-3-haiku-20240307"
TEMPERATURE = 0.25
MAX_TOKENS = 1000


def get_db(db_path: Path) -> sqlite3.Connection:
    db = sqlite3.connect(db_path, detect_types=sqlite3.PARSE_DECLTYPES)
    db.row_factory = sqlite3.Row
    return db


def choose_prompt(app: str) -> str:
    available_prompts = get_available_prompts(app)

    print("Available prompts:")
    for i, (name, _) in enumerate(available_prompts.items(), 1):
        print(f"{i}. {name}")

    choice = input("Select a prompt (by number): ")
    index = int(choice) - 1
    return list(available_prompts.keys())[index]


def cli_load_data(args: argparse.Namespace) -> None:
    db = get_db(args.db_path)
    file_path = args.file_path
    app = args.app
    prompt_name = choose_prompt(app)
    load_data(db, file_path, app, prompt_name)


def load_data(db: sqlite3.Connection, file_path: Path, app: str, prompt_name: str) -> None:
    # Load data
    queries, headers = load_queries(file_path)

    prompt_func, fields = load_prompt(app, prompt_name, headers)

    cur = db.execute("INSERT INTO prompt_set(query_src_file, prompt_func) VALUES (?, ?)", [file_path.name, prompt_name])
    db.commit()
    prompt_set_id = cur.lastrowid

    match prompt_name:
        case "make_sufficient_prompt":
            model_field = "insufficient_model"
        case "make_main_prompt":
            model_field = "main_model"
        case _:
            raise ValueError(f"Unknown prompt name: {prompt_name}")

    # Generate prompts and store them
    for query in queries:
        prompt_msgs = make_prompt(prompt_func, query)
        db.execute(
            "INSERT INTO prompt(msgs_json, model_response, set_id) VALUES(?, ?, ?)",
            [json.dumps(prompt_msgs), query[model_field], prompt_set_id]
        )
        db.commit()

    print(f"{len(queries)} prompts inserted, prompt set ID = {prompt_set_id}.")


def choose_prompt_set(db: sqlite3.Connection) -> int:
    prompt_sets = db.execute("SELECT * FROM prompt_set").fetchall()

    print("Prompt sets:")
    for prompt_set in prompt_sets:
        print(f"{prompt_set['id']}: {prompt_set['created']} - {prompt_set['query_src_file']} {prompt_set['prompt_func']}")
    prompt_set_id = int(input("Select a prompt set (by ID): "))

    return prompt_set_id


def cli_gen_responses(args: argparse.Namespace) -> None:
    db = get_db(args.db_path)
    prompt_set_id = choose_prompt_set(db)
    gen_responses(db, prompt_set_id, args.model)


def gen_responses(db: sqlite3.Connection, prompt_set_id: int, model: str) -> None:
    cur = db.execute("INSERT INTO response_set(model, prompt_set_id) VALUES (?, ?)", [model, prompt_set_id])
    db.commit()
    response_set_id = cur.lastrowid

    prompts = db.execute("SELECT * FROM prompt WHERE set_id=?", [prompt_set_id]).fetchall()

    for prompt in tqdm(prompts, ncols=60):
        msgs = json.loads(prompt['msgs_json'])
        try:
            response = litellm.completion(
                model=model,
                messages=msgs,
                temperature=TEMPERATURE,
                max_tokens=MAX_TOKENS,
                n=1,
            )
            response_json = json.dumps(response.model_dump())
            text = response.choices[0].message.content
        except Exception as e:  # noqa
            text = f"[An error occurred in the completion.]\n{e}"
            tqdm.write(f"\x1B[31m{text}\x1B[m")
            response_json = json.dumps(text)

        db.execute(
            "INSERT INTO response(set_id, prompt_id, response, text) VALUES(?, ?, ?, ?)",
            [response_set_id, prompt['id'], response_json, text]
        )
        db.commit()

        # hack for now for Claude rate limits
        if "sonnet" in model:
            time.sleep(0.25)


def choose_response_set(db: sqlite3.Connection, eval_model: str) -> tuple[int, str]:
    response_sets = db.execute("""
        SELECT response_set.id, response_set.created, response_set.model, prompt_set.query_src_file, prompt_set.prompt_func, eval_set.model==? AS eval_with_this_model
        FROM response_set
        JOIN prompt_set ON response_set.prompt_set_id=prompt_set.id
        LEFT JOIN eval_set ON eval_set.response_set_id=response_set.id AND eval_set.model=?
        ORDER BY response_set.created
    """, [eval_model, eval_model]).fetchall()

    funcs: dict[int, str] = {}
    allowed_ids: list[int] = []  # only allow running an eval that hasn't already been done with this model

    print("Response sets:")
    for response_set in response_sets:
        already_evaled = response_set['eval_with_this_model']
        if not already_evaled:
            allowed_ids.append(response_set['id'])
        else:
            print("\x1B[30;1m", end='')  # grayed out
        print(f"{response_set['id']}: {response_set['created']} - {response_set['query_src_file']} {response_set['prompt_func']} -> {response_set['model']}")
        print("\x1B[m", end='')
        funcs[response_set['id']] = response_set['prompt_func']

    response_set_id = int(input("Select a response set (by ID): "))

    if response_set_id not in allowed_ids:
        print(f"That response set has already been evaluated with {eval_model}!")
        sys.exit(1)

    return response_set_id, funcs[response_set_id]


_SUFFICIENT_SYS_PROMPT = """\
You are an automated system grading responses given to a student who requested help in a CS class.

Evaluate the given response (in <response> delimiters) by comparing it to the given model (in <model> delimiters).

An ideal response will request or mention every individual point in the model.

For each specific point in the model, evaluate whether it is covered in the response.

Output a JSON object with a key for each point, mapping each to true if the point is covered and false otherwise.

Output nothing after the JSON.
"""


def eval_sufficient(model: str, row: Row) -> dict[str, bool]:
    response = row['text']
    model_response = row['model_response']
    if model_response == "OK.":
        # special case; can check with simple text processing
        return {"OK.": "OK." in response}
    elif "OK." in response:
        # And if the model response is *not* "OK." but the real response includes it,
        # we immediately know that's incorrect.
        return {x: False for x in model_response.splitlines()}

    msgs = [
        {"role": "system", "content": _SUFFICIENT_SYS_PROMPT},
        {"role": "user", "content": f"<response>\n{response}\n</response>\n\n<model>\n{model_response}\n</model>"},
    ]
    litellm.drop_params = True  # still run if 'response_format' not accepted by the current model
    response = litellm.completion(
        model=model,
        response_format={ "type": "json_object" },
        messages=msgs,
        temperature=TEMPERATURE,
        max_tokens=MAX_TOKENS,
        n=1,
    )
    litellm.drop_params = False  # reset to default
    text = response.choices[0].message.content

    try:
        return json.loads(text)
    except json.decoder.JSONDecodeError:
        print(f"\x1B[31;1mInvalid:\x1B[m\n\x1B[33m{text}\x1B[m")
        raise


def cli_gen_evals(args: argparse.Namespace) -> None:
    db = get_db(args.db_path)
    response_set_id, prompt_func = choose_response_set(db, args.model)
    gen_evals(db, args.model, response_set_id, prompt_func)


def gen_evals(db: sqlite3.Connection, model: str, response_set_id: int, prompt_func: str) -> None:
    rows = db.execute("SELECT response.id, response.text, prompt.model_response FROM response JOIN prompt ON response.prompt_id=prompt.id WHERE response.set_id=?", [response_set_id]).fetchall()

    match prompt_func:
        case "make_sufficient_prompt":
            sys_prompt = _SUFFICIENT_SYS_PROMPT
            eval_func = eval_sufficient
            summarize_func = summarize_eval_insufficient

    # Add system prompt if not used previously, get its ID
    # SET id=id is no-op, but we need to do an update so we can get the id using RETURNING
    cur = db.execute("INSERT INTO eval_prompt (sys_prompt) VALUES (?) ON CONFLICT DO UPDATE SET id=id RETURNING id", [sys_prompt])
    eval_prompt_id = cur.fetchone()['id']
    db.commit()

    # Create an eval set
    cur = db.execute("INSERT INTO eval_set (response_set_id, eval_prompt_id, model) VALUES (?, ?, ?)", [response_set_id, eval_prompt_id, model])
    eval_set_id = cur.lastrowid
    assert(eval_set_id)

    # Generate and add the evaluations
    for row in tqdm(rows, ncols=60):
        evaluation = eval_func(model, row)
        db.execute("INSERT INTO eval (set_id, response_id, evaluation) VALUES (?, ?, ?)", [eval_set_id, row['id'], json.dumps(evaluation)])

        if False in evaluation.values():
            tqdm.write(row['text'])
            tqdm.write(str(evaluation))

    db.commit()  # only commit if we've generated all rows

    summarize_func(db, eval_set_id)


def summarize_eval_insufficient(db: sqlite3.Connection, eval_set_id: int) -> None:
    eval_rows = db.execute("SELECT * FROM eval WHERE set_id=?", [eval_set_id]).fetchall()

    evals = [json.loads(row['evaluation']) for row in eval_rows]

    #print(f"{len(evals)} evaluations.  {len(all_points)} points.  {ok_total} OK.  {other_total} Other.")
    ok_true = sum(eval_dict.get("OK.") == True for eval_dict in evals)
    ok_false = sum(eval_dict.get("OK.") == False for eval_dict in evals)
    print(f"    OK.: \x1B[32m{'-' * ok_true}\x1B[31m{'-' * ok_false}\x1B[m  {ok_true}/{ok_false}")
    other_true = sum(sum(eval_dict.get(key) == True for key in eval_dict if key != "OK.") for eval_dict in evals)
    other_false = sum(sum(eval_dict.get(key) == False for key in eval_dict if key != "OK.") for eval_dict in evals)
    print(f"  Other: \x1B[32m{'-' * other_true}\x1B[31m{'-' * other_false}\x1B[m  {other_true}/{other_false}")


def show_evals(args: argparse.Namespace) -> None:
    if args.eval_set is None:
        show_all_evals(args)
    else:
        show_one_eval(args)


def show_one_eval(args: argparse.Namespace) -> None:
    db = get_db(args.db_path)

    eval_rows = db.execute("SELECT * FROM eval JOIN response ON response.id=eval.response_id JOIN prompt ON prompt.id=response.prompt_id WHERE eval.set_id = ?", [args.eval_set]).fetchall()
    for row in eval_rows:
        if False in json.loads(row['evaluation']).values():  # check if points evaluated as False
            print(f"\x1B[33m{row['text']}\x1B[m")
            print(f"\x1B[36m{row['evaluation']}\x1B[m")

    summarize_eval_insufficient(db, args.eval_set)

def show_all_evals(args: argparse.Namespace) -> None:
    db = get_db(args.db_path)

    eval_set_rows = db.execute("""
        SELECT eval_set.*, response_set.model AS response_model, prompt_set.prompt_func, prompt_set.created AS prompt_created
        FROM eval_set
        JOIN response_set ON response_set.id=eval_set.response_set_id
        JOIN prompt_set ON prompt_set.id=response_set.prompt_set_id
    """
        + ("ORDER BY prompt_set.prompt_func, prompt_set.created, response_set.model" if args.by_prompt
          else "ORDER BY prompt_set.prompt_func, response_set.model, prompt_set.created")
    ).fetchall()

    for row in eval_set_rows:
        print(f"{row['id']}: \x1B[36m{row['prompt_func']}+{row['prompt_created']}\x1B[m (response: \x1B[33m{row['response_model']}\x1B[m) \x1B[30;1m(eval: {row['model']})\x1B[m")

        eval_set_id = row['id']

        summarize_eval_insufficient(db, eval_set_id)


def main() -> None:
    parser = argparse.ArgumentParser(description='A tool for running queries against data from a CSV/ODS/XLSX file and evaluating a model\'s responses.')
    parser.add_argument('app', type=str, help='The name of the application module from which to load prompts (e.g., codehelp or starburst).')
    parser.add_argument('db_path', type=Path, help='Path to the database file storing prompts and evaluations.')
    subparsers = parser.add_subparsers(required=True)

    parser_load = subparsers.add_parser('load', help='Load a file of queries and model responses; store a generated set of prompts in the database.')
    parser_load.set_defaults(command_func=cli_load_data)
    parser_load.add_argument('file_path', type=Path, help='Path to the file to be read.')

    parser_response = subparsers.add_parser('response', help='Generate a response set for a given prompt set.')
    parser_response.set_defaults(command_func=cli_gen_responses)
    parser_response.add_argument(
        'model', type=str, nargs='?', default=DEFAULT_MODEL,
        help=f"(Optional. Default='{DEFAULT_MODEL}')  The LLM to use."
    )

    parser_eval = subparsers.add_parser('eval', help='Evaluate a given response set.')
    parser_eval.set_defaults(command_func=gen_evals)
    parser_eval.add_argument(
        'model', type=str, nargs='?', default=DEFAULT_MODEL,
        help=f"(Optional. Default='{DEFAULT_MODEL}')  The LLM to use."
    )

    parser_show_evals = subparsers.add_parser('show_evals', help="Display the results of past evals.")
    parser_show_evals.set_defaults(command_func=show_evals)
    parser_show_evals.add_argument('--by-prompt', action='store_true', help="Order the evaluations by the prompt used (default: order by model, then prompt)")
    parser_show_evals.add_argument('eval_set', nargs='?', type=int, help="Show details of the given evaluation set.")

    args = parser.parse_args()

    if 'model' in args:
        test_and_report_model(args.model)

    # run the function associated with the chosen command
    args.command_func(args)


if __name__ == '__main__':
    main()
