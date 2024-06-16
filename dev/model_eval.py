#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2024 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

import argparse
import json
import sqlite3
from pathlib import Path

from loaders import load_prompt, load_queries, make_prompt, setup_openai

TEMPERATURE = 0.25
MAX_TOKENS = 1000


def get_db(db_path):
    db = sqlite3.connect(db_path, detect_types=sqlite3.PARSE_DECLTYPES)
    db.row_factory = sqlite3.Row
    return db


def load_data(args):
    db = get_db(args.db_path)

    # Load data
    queries, headers = load_queries(args.file_path)

    # Initialize the prompt
    prompt_func, fields = load_prompt(args.app, headers)

    cur = db.execute("INSERT INTO prompt_set(query_src_file, prompt_func) VALUES (?, ?)", [args.file_path.name, prompt_func.__name__])
    db.commit()
    prompt_set_id = cur.lastrowid

    match prompt_func.__name__:
        case "make_sufficient_prompt":
            model_field = "insufficient_model"
        case "make_main_prompt":
            model_field = "main_model"

    # Generate prompts and store them
    for query in queries:
        prompt_msgs = make_prompt(prompt_func, query)
        db.execute(
            "INSERT INTO prompt(msgs_json, model_response, set_id) VALUES(?, ?, ?)",
            [json.dumps(prompt_msgs), query[model_field], prompt_set_id]
        )
        db.commit()

    print(f"{len(queries)} prompts inserted, prompt set ID = {prompt_set_id}.")


def choose_prompt_set(db) -> int:
    prompt_sets = db.execute("SELECT * FROM prompt_set").fetchall()

    print("Prompt sets:")
    for prompt_set in prompt_sets:
        print(f"{prompt_set['id']}: {prompt_set['created']} - {prompt_set['query_src_file']} {prompt_set['prompt_func']}")
    prompt_set_id = int(input("Select a prompt set (by ID): "))

    return prompt_set_id


def gen_responses(args):
    db = get_db(args.db_path)

    prompt_set_id = choose_prompt_set(db)

    client = setup_openai()

    cur = db.execute("INSERT INTO response_set(model, prompt_set_id) VALUES (?, ?)", [args.model, prompt_set_id])
    db.commit()
    response_set_id = cur.lastrowid

    prompts = db.execute("SELECT * FROM prompt WHERE set_id=?", [prompt_set_id]).fetchall()

    for i, prompt in enumerate(prompts):
        msgs = json.loads(prompt['msgs_json'])
        try:
            response = client.chat.completions.create(
                model=args.model,
                messages=msgs,
                temperature=TEMPERATURE,
                max_tokens=MAX_TOKENS,
                n=1,
            )
            text = response.choices[0].message.content
        except Exception as e:  # noqa
            response = f"[An error occurred in the openai completion.]\n{e}"
            text = response

        db.execute(
            "INSERT INTO response(set_id, prompt_id, response, text) VALUES(?, ?, ?, ?)",
            [response_set_id, prompt['id'], json.dumps(response.model_dump()), text]
        )
        print(f"{i+1}/{len(prompts)}")
        db.commit()


def choose_response_set(db) -> int:
    response_sets = db.execute("SELECT response_set.id, response_set.created, response_set.model, prompt_set.query_src_file, prompt_set.prompt_func FROM response_set JOIN prompt_set ON response_set.prompt_set_id=prompt_set.id").fetchall()

    funcs = {}

    print("Response sets:")
    for response_set in response_sets:
        print(f"{response_set['id']}: {response_set['created']} - {response_set['query_src_file']} {response_set['prompt_func']} -> {response_set['model']}")
        funcs[response_set['id']] = response_set['prompt_func']

    response_set_id = int(input("Select a response set (by ID): "))

    return response_set_id, funcs[response_set_id]


def eval_sufficient(client, model, row):
    response = row['text']
    model_response = row['model_response']
    if model_response == "OK.":
        # special case; can check with simple text processing
        return {"OK.": "OK." in response}

    msgs = [
        {"role": "system", "content": """\
Evaluate the given text (in <text> delimiters) by comparing it to the given model (in <model> delimiters).

For each specific point in the model, evaluate whether it is addressed or mentioned in the text.  Output a JSON object with a key for each point, mapping each to true if the point is included and false otherwise."""},
        {"role": "user", "content": f"<text>\n{response}\n</text>\n\n<model>\n{model_response}\n</model>"},
    ]
    response = client.chat.completions.create(
        model=model,
        response_format={ "type": "json_object" },
        messages=msgs,
        temperature=TEMPERATURE,
        max_tokens=MAX_TOKENS,
        n=1,
    )
    text = response.choices[0].message.content
    return json.loads(text)


def gen_evals(args):
    client = setup_openai()

    db = get_db(args.db_path)

    response_set_id, prompt_func = choose_response_set(db)

    rows = db.execute("SELECT response.text, prompt.model_response FROM response JOIN prompt ON response.prompt_id=prompt.id WHERE response.set_id=?", [response_set_id]).fetchall()

    match prompt_func:
        case "make_sufficient_prompt":
            eval_func = eval_sufficient

    evals = []

    for i, row in enumerate(rows):
        evaluation = eval_func(client, args.model, row)
        evals.append(evaluation)
        print(f"{i+1}/{len(rows)}")
        if False in evaluation.values():
            print(row['text'])
            print(evaluation)

    ok_true = sum(eval_dict.get("OK.") == True for eval_dict in evals)
    ok_false = sum(eval_dict.get("OK.") == False for eval_dict in evals)
    print(f"OK.:   {ok_true} true, {ok_false} false")
    other_true = sum(sum(eval_dict.get(key) == True for key in eval_dict if key != "OK.") for eval_dict in evals)
    other_false = sum(sum(eval_dict.get(key) == False for key in eval_dict if key != "OK.") for eval_dict in evals)
    print(f"Other: {other_true} true, {other_false} false")


def main() -> None:
    parser = argparse.ArgumentParser(description='A tool for running queries against data from a CSV/ODS/XLSX file and evaluating a model\'s responses.')
    parser.add_argument('app', type=str, help='The name of the application module from which to load prompts (e.g., codehelp or starburst).')
    parser.add_argument('db_path', type=Path, help='Path to the database file storing prompts and evaluations.')
    subparsers = parser.add_subparsers(required=True)
    parser_load = subparsers.add_parser('load', help='Load a file of queries and model responses; store a generated set of prompts in the database.')
    parser_load.add_argument('file_path', type=Path, help='Path to the file to be read.')
    parser_load.set_defaults(command_func=load_data)
    parser_response = subparsers.add_parser('response', help='Generate a response set for a given prompt set.')
    parser_response.add_argument(
        'model', type=str, nargs='?', default='gpt-3.5-turbo',
        help='(Optional. Default="gpt-3.5-turbo")  The LLM to use (gpt-{3.5-turbo, 4o, etc.}).'
    )
    parser_response.set_defaults(command_func=gen_responses)
    parser_eval = subparsers.add_parser('eval', help='Evaluate a given response set.')
    parser_eval.add_argument(
        'model', type=str, nargs='?', default='gpt-3.5-turbo',
        help='(Optional. Default="gpt-3.5-turbo")  The LLM to use (gpt-{3.5-turbo, 4o, etc.}).'
    )
    parser_eval.set_defaults(command_func=gen_evals)
    args = parser.parse_args()

    # run the function associated with the chosen command
    args.command_func(args)


if __name__ == '__main__':
    main()
