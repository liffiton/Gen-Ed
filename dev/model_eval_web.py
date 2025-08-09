#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2024 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

import json
import os
import re
import sqlite3
from pathlib import Path
from secrets import token_bytes

from flask import Flask, flash, redirect, render_template, request, session, url_for
from loaders import get_available_prompts
from markdown_it import MarkdownIt
from markupsafe import Markup
from model_eval import gen_evals as gen_evals_func
from model_eval import gen_responses as gen_responses_func
from model_eval import load_data as load_data_func
from werkzeug.wrappers.response import Response

app = Flask(__name__)
app.secret_key = token_bytes(16)  # randomizes each startup -- fine for a dev tool

# Configuration
app.config['DATA_DIR'] = Path('data')
app.config['DB_PATH'] = app.config['DATA_DIR'] / 'model_evals.db'

# Database connection
def get_db() -> sqlite3.Connection:
    db = sqlite3.connect(app.config['DB_PATH'], detect_types=sqlite3.PARSE_DECLTYPES)
    db.row_factory = sqlite3.Row
    return db

@app.route('/', methods=['GET', 'POST'])
def home() -> str | Response:
    if request.method == 'POST':
        session['app'] = request.form['app']
        return redirect(url_for('home'))
    return render_template('home.html', app=session.get('app'))

@app.route('/select_file')
def select_file() -> str | Response:
    if 'app' not in session:
        return redirect(url_for('home'))

    files = [f for f in os.listdir(app.config['DATA_DIR']) if f.endswith(('.csv', '.ods', '.xlsx'))]
    return render_template('select_file.html', app=session['app'], files=files)

@app.route('/select_prompt')
def select_prompt() -> str | Response:
    if 'app' not in session:
        return redirect(url_for('home'))

    selected_file = request.args.get('file')
    if selected_file:
        file_path = app.config['DATA_DIR'] / selected_file
        if file_path.exists():
            available_prompts = get_available_prompts(session['app'])

            return render_template('select_prompt.html',
                                    app=session['app'],
                                    file=selected_file,
                                    prompts=available_prompts)
        else:
            flash("Selected file does not exist.", "danger")

    return redirect(url_for('select_file'))

@app.route('/load_data', methods=['POST'])
def load_data() -> str | Response:
    if 'app' not in session:
        return redirect(url_for('home'))

    selected_file = request.form.get('file')
    selected_prompt = request.form.get('prompt')

    if not selected_file or not selected_prompt:
        flash("Missing required argument.", "danger")
        return redirect(url_for('select_file'))

    db = get_db()
    file_path = app.config['DATA_DIR'] / selected_file

    try:
        load_data_func(db, file_path, session['app'], selected_prompt)
    except ValueError as e:
        flash(str(e), "danger")
        return redirect(url_for('select_file'))

    flash("Data loaded successfully.", "success")
    return redirect(url_for('home'))


@app.route('/generate_responses', methods=['POST'])
def generate_responses() -> Response:
    db = get_db()
    prompt_set_id = int(request.form['prompt_set'])
    model = request.form['model']

    if matches := re.match(r"^(.+) +\((.+)\)$", model):
        model = matches[1]
        reasoning_effort = matches[2]
    else:
        reasoning_effort = None

    gen_responses_func(db, prompt_set_id, model, reasoning_effort)
    flash(f"Responses generated successfully for prompt set {prompt_set_id} using {model}.", "success")
    return redirect(url_for('dashboard'))

@app.route('/evaluate_responses', methods=['POST'])
def evaluate_responses() -> Response:
    db = get_db()
    response_set_id = int(request.form['response_set'])

    cur = db.execute("SELECT id FROM response_set WHERE response_set.id=?", [response_set_id])
    row = cur.fetchone()
    if not row:
        flash(f"Could not find response set with id {response_set_id} to evaluate.", "danger")
        return redirect(url_for('dashboard'))

    response_set_id = row['id']
    eval_model = "gemini/gemini-2.0-flash"   # TODO: un-hardcode evaluating model
    gen_evals_func(db, eval_model, response_set_id, "make_sufficient_prompt")  # TODO: un-hardcode prompt type
    flash(f"Responses evaluated successfully for response set {response_set_id}.", "success")
    return redirect(url_for('dashboard'))


@app.template_filter('percentage')
def percentage_filter(value: int, total: int) -> str:
    return f"{(value / total * 100):.1f}%" if total > 0 else "N/A"

@app.route('/view_false_responses/<int:eval_set_id>')
def view_false_responses(eval_set_id: int) -> str:
    db = get_db()

    # Fetch eval set details
    eval_set = db.execute("""
        SELECT eval_set.*, response_set.model AS response_model, prompt_set.prompt_func
        FROM eval_set
        JOIN response_set ON response_set.id = eval_set.response_set_id
        JOIN prompt_set ON prompt_set.id = response_set.prompt_set_id
        WHERE eval_set.id = ?
    """, [eval_set_id]).fetchone()

    # Fetch responses that evaluated as False
    false_responses = db.execute("""
        SELECT response.text, response.response_time,
               response.prompt_tokens, response.reasoning_tokens, response.completion_tokens,
               eval.evaluation, prompt.model_response
        FROM eval
        JOIN response ON response.id = eval.response_id
        JOIN prompt ON prompt.id = response.prompt_id
        WHERE eval.set_id = ? AND eval.evaluation LIKE '%false%'
    """, [eval_set_id]).fetchall()

    false_responses = [
        {
            'text': row['text'],
            'response_time': row['response_time'],
            'prompt_tokens': row['prompt_tokens'],
            'reasoning_tokens': row['reasoning_tokens'],
            'completion_tokens': row['completion_tokens'],
            'evaluation': json.loads(row['evaluation']),
            'model_response': row['model_response']
        }
        for row in false_responses
    ]

    return render_template('view_false_responses.html', eval_set=eval_set, false_responses=false_responses)

@app.route('/compare_responses')
def compare_responses() -> Response | str:
    db = get_db()

    # Get the selected response sets from the query parameters
    set1 = request.args.get('set1')
    set2 = request.args.get('set2')

    if not set1 or not set2:
        flash("Please select two response sets to compare.", "danger")
        return redirect(url_for('dashboard'))

    try:
        set1_id = int(set1)
        set2_id = int(set2)
    except TypeError as e:
        flash(f"Error processing comparison request: {e!s}", "danger")
        return redirect(url_for('dashboard'))

    set1_row = db.execute("SELECT * FROM response_set WHERE id = ?", [set1_id]).fetchone()
    set2_row = db.execute("SELECT * FROM response_set WHERE id = ?", [set2_id]).fetchone()

    if not set1_row or not set2_row:
        flash("One or both of the selected response sets could not be found.", "danger")
        return redirect(url_for('dashboard'))

    # Check if both response sets are from the same prompt set
    prompt_set_id1 = set1_row['prompt_set_id']
    prompt_set_id2 = set2_row['prompt_set_id']

    if prompt_set_id1 != prompt_set_id2:
        flash("The selected response sets must be from the same prompt set for comparison.", "danger")
        return redirect(url_for('dashboard'))

    # Get prompt set details
    prompt_set = db.execute("""
        SELECT prompt_set.id, prompt_set.created, prompt_set.query_src_file, prompt_set.prompt_func
        FROM prompt_set
        WHERE prompt_set.id = ?
    """, [prompt_set_id1]).fetchone()

    # Get all prompts from this prompt set
    prompts = db.execute("""
        SELECT prompt.id, prompt.msgs_json, prompt.model_response
        FROM prompt
        WHERE prompt.set_id = ?
        ORDER BY prompt.id
    """, [prompt_set_id1]).fetchall()

    if not prompts:
        flash("No prompts found in the selected prompt set.", "danger")
        return redirect(url_for('dashboard'))

    # Get responses for both models
    responses1 = db.execute("""
        SELECT response.prompt_id, response.text, response.response_time,
               response.prompt_tokens, response.reasoning_tokens, response.completion_tokens
        FROM response
        WHERE response.set_id = ?
    """, [set1_id]).fetchall()

    responses2 = db.execute("""
        SELECT response.prompt_id, response.text, response.response_time,
               response.prompt_tokens, response.reasoning_tokens, response.completion_tokens
        FROM response
        WHERE response.set_id = ?
    """, [set2_id]).fetchall()

    # Get evaluation results if available
    eval_set1 = db.execute("""
        SELECT eval_set.id
        FROM eval_set
        WHERE eval_set.response_set_id = ?
    """, [set1_id]).fetchone()

    eval_set2 = db.execute("""
        SELECT eval_set.id
        FROM eval_set
        WHERE eval_set.response_set_id = ?
    """, [set2_id]).fetchone()

    evals1 = {}
    evals2 = {}

    if eval_set1:
        eval_results1 = db.execute("""
            SELECT eval.response_id, eval.evaluation
            FROM eval
            JOIN response ON response.id = eval.response_id
            WHERE eval.set_id = ?
        """, [eval_set1['id']]).fetchall()

        for eval_result in eval_results1:
            response_id = eval_result['response_id']
            prompt_id = db.execute("SELECT prompt_id FROM response WHERE id = ?", [response_id]).fetchone()['prompt_id']
            evals1[prompt_id] = json.loads(eval_result['evaluation'])

    if eval_set2:
        eval_results2 = db.execute("""
            SELECT eval.response_id, eval.evaluation
            FROM eval
            JOIN response ON response.id = eval.response_id
            WHERE eval.set_id = ?
        """, [eval_set2['id']]).fetchall()

        for eval_result in eval_results2:
            response_id = eval_result['response_id']
            prompt_id = db.execute("SELECT prompt_id FROM response WHERE id = ?", [response_id]).fetchone()['prompt_id']
            evals2[prompt_id] = json.loads(eval_result['evaluation'])

    # Create a mapping of prompt_id to responses and evaluations
    comparison_data = []

    # Jinja filter for converting Markdown to HTML
    markdown_processor = MarkdownIt("js-default")  # js-default: https://markdown-it-py.readthedocs.io/en/latest/security.html
    markdown_processor.inline.ruler.disable(['escape'])  # disable escaping so that \(, \[, etc. come through for TeX math

    def markdown(value: str) -> str:
        '''Convert markdown to HTML.'''
        html = markdown_processor.render(value)
        # relying on MarkdownIt's escaping (w/o HTML parsing, due to "js-default"), so mark this as safe
        return Markup(html)

    for prompt in prompts:
        prompt_id = prompt['id']

        # Find corresponding responses
        response1 = next((r for r in responses1 if r['prompt_id'] == prompt_id), None)
        response2 = next((r for r in responses2 if r['prompt_id'] == prompt_id), None)

        comparison_data.append({
            'prompt_id': prompt_id,
            'prompt_msgs': json.loads(prompt['msgs_json']),
            'model_response': prompt['model_response'],
            'response1': {
                'text': markdown(response1['text']) if response1 else "No response",
                'response_time': response1['response_time'] if response1 else None,
                'prompt_tokens': response1['prompt_tokens'] if response1 else None,
                'reasoning_tokens': response1['reasoning_tokens'] if response1 else None,
                'completion_tokens': response1['completion_tokens'] if response1 else None,
                'evaluation': evals1.get(prompt_id, {})
            },
            'response2': {
                'text': markdown(response2['text']) if response2 else "No response",
                'response_time': response2['response_time'] if response2 else None,
                'prompt_tokens': response2['prompt_tokens'] if response2 else None,
                'reasoning_tokens': response2['reasoning_tokens'] if response2 else None,
                'completion_tokens': response2['completion_tokens'] if response2 else None,
                'evaluation': evals2.get(prompt_id, {})
            }
        })

    return render_template('compare_responses.html',
                            prompt_set=prompt_set,
                            model1=set1_row['model'],
                            model2=set2_row['model'],
                            comparison_data=comparison_data)


@app.route('/dashboard')
def dashboard() -> str:
    db = get_db()

    # 1. Get all prompt sets with counts
    prompt_sets = db.execute("""
        SELECT ps.id, ps.created, ps.query_src_file, ps.prompt_func, COUNT(p.id) as prompt_count
        FROM prompt_set ps
        LEFT JOIN prompt p ON ps.id = p.set_id
        GROUP BY ps.id
        ORDER BY ps.created DESC
    """).fetchall()

    # 2. Get all unique models used in response sets
    models_query = db.execute("SELECT DISTINCT model FROM response_set ORDER BY model").fetchall()
    models = [row['model'] for row in models_query]

    # 3. Fetch all response sets, eval sets, and stats, keyed for lookup
    response_sets_raw = db.execute("""
        SELECT
            rs.id as response_set_id, rs.prompt_set_id, rs.model,
            MIN(r.response_time) as min_time,
            AVG(r.response_time) as avg_time,
            MAX(r.response_time) as max_time,
            COUNT(r.response_time) as count_with_time,
            MIN(r.prompt_tokens) as min_prompt_tokens,
            AVG(r.prompt_tokens) as avg_prompt_tokens,
            MAX(r.prompt_tokens) as max_prompt_tokens,
            MIN(r.completion_tokens) as min_completion_tokens,
            AVG(r.completion_tokens) as avg_completion_tokens,
            MAX(r.completion_tokens) as max_completion_tokens,
            MIN(r.reasoning_tokens) as min_reasoning_tokens,
            AVG(r.reasoning_tokens) as avg_reasoning_tokens,
            MAX(r.reasoning_tokens) as max_reasoning_tokens
        FROM response_set rs
        LEFT JOIN response r ON r.set_id = rs.id AND r.response_time IS NOT NULL
        GROUP BY rs.id, rs.prompt_set_id, rs.model
    """).fetchall()

    eval_sets_raw = db.execute("""
        SELECT
            es.id as eval_set_id, es.response_set_id, es.model as eval_model,
            SUM(CASE WHEN json_extract(e.evaluation, '$.\"OK.\"') = 1 THEN 1 ELSE 0 END) as ok_true,
            SUM(CASE WHEN json_extract(e.evaluation, '$.\"OK.\"') = 0 THEN 1 ELSE 0 END) as ok_false,
            -- Correctly count the remaining keys after removing "OK."
            SUM(
                (
                    SELECT COUNT(*)
                    FROM json_each(json_remove(e.evaluation, '$.\"OK.\"'))
                    -- No WHERE clause needed, just count all remaining keys
                )
            ) as other_total,
            SUM(
                (
                    SELECT COUNT(*)
                    FROM json_each(json_remove(e.evaluation, '$.\"OK.\"'))
                    WHERE value = 1
                )
            ) as other_true
        FROM eval_set es
        JOIN eval e ON e.set_id = es.id
        GROUP BY es.id, es.response_set_id, es.model
    """).fetchall()

    # 4. Structure data for the template: cell_data[prompt_set_id][model] = { ... }
    cell_data: dict[int, dict[str, dict]] = {}

    # Populate with response set info and times
    for rs_row in response_sets_raw:
        ps_id = rs_row['prompt_set_id']
        model = rs_row['model']
        if ps_id not in cell_data:
            cell_data[ps_id] = {}

        cell_data[ps_id][model] = {
            'status': 'generated',
            'response_set_id': rs_row['response_set_id'],
            'stats': None,
            'eval_stats': None,
            'eval_model': None,
            'eval_set_id': None
        }
        if rs_row['count_with_time'] > 0:
             cell_data[ps_id][model]['stats'] = {
                'count': rs_row['count_with_time'],
                'time': {
                    'min': rs_row['min_time'],
                    'avg': rs_row['avg_time'],
                    'max': rs_row['max_time'],
                } if rs_row['min_time'] is not None else None,
                'prompt': {
                    'min': rs_row['min_prompt_tokens'],
                    'avg': rs_row['avg_prompt_tokens'],
                    'max': rs_row['max_prompt_tokens'],
                } if rs_row['min_prompt_tokens'] is not None else None,
                'completion': {
                    'min': rs_row['min_completion_tokens'],
                    'avg': rs_row['avg_completion_tokens'],
                    'max': rs_row['max_completion_tokens'],
                } if rs_row['min_completion_tokens'] is not None else None,
                'reasoning': {
                    'min': rs_row['min_reasoning_tokens'],
                    'avg': rs_row['avg_reasoning_tokens'],
                    'max': rs_row['max_reasoning_tokens'],
                } if rs_row['min_reasoning_tokens'] is not None else None,
            }

    # Update with evaluation info
    for es_row in eval_sets_raw:
        # Find the corresponding response set to link back to prompt_set_id and model
        response_set_info = next((rs for rs in response_sets_raw if rs['response_set_id'] == es_row['response_set_id']), None)
        if not response_set_info:
            # This might happen if a response set exists but has no responses with response_time,
            # causing it to be missed by the response_sets_raw query if it also has no evals yet.
            # Let's try fetching it directly.
            rs_direct = db.execute("SELECT prompt_set_id, model FROM response_set WHERE id = ?", [es_row['response_set_id']]).fetchone()
            if rs_direct:
                response_set_info = {'prompt_set_id': rs_direct['prompt_set_id'], 'model': rs_direct['model'], 'response_set_id': es_row['response_set_id']}
            else:
                 # If still not found, skip this eval set (orphan?)
                print(f"Warning: Could not find response set for eval_set_id {es_row['eval_set_id']}")
                continue

        ps_id = response_set_info['prompt_set_id']
        model = response_set_info['model']

        # Ensure the base entry exists if it wasn't created by the response_sets_raw query
        if ps_id not in cell_data:
            cell_data[ps_id] = {}
        if model not in cell_data[ps_id]:
             cell_data[ps_id][model] = {
                'status': 'generated', # Assume generated if evaluated
                'response_set_id': response_set_info['response_set_id'],
                'stats': None, # No timing info from this query path
                'eval_stats': None,
                'eval_model': None,
                'eval_set_id': None
            }


        if ps_id in cell_data and model in cell_data[ps_id]:
            cell_data[ps_id][model]['status'] = 'evaluated'
            cell_data[ps_id][model]['eval_set_id'] = es_row['eval_set_id']
            cell_data[ps_id][model]['eval_model'] = es_row['eval_model']

            # Calculate derived stats
            ok_true = es_row['ok_true'] or 0
            ok_false = es_row['ok_false'] or 0
            other_true = es_row['other_true'] or 0
            # Handle potential NULL from SUM if no 'other' keys exist
            other_total_raw = es_row['other_total']
            other_total = other_total_raw if other_total_raw is not None else 0
            other_false = other_total - other_true

            cell_data[ps_id][model]['eval_stats'] = {
                'ok_true': ok_true,
                'ok_false': ok_false,
                'ok_total': ok_true + ok_false,
                'other_true': other_true,
                'other_false': other_false,
                'other_total': other_total,
            }


    return render_template('dashboard.html',
                           prompt_sets=prompt_sets,
                           models=models,
                           cell_data=cell_data)
