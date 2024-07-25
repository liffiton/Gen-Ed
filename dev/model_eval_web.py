import json
import os
import sqlite3
from pathlib import Path
from secrets import token_bytes

from flask import Flask, flash, redirect, render_template, request, session, url_for
from loaders import get_available_prompts, load_queries
from model_eval import gen_evals as gen_evals_func
from model_eval import gen_responses as gen_responses_func
from model_eval import load_data as load_data_func

app = Flask(__name__)
app.secret_key = token_bytes(16)  # randomizes each startup -- fine for a dev tool

# Configuration
app.config['DATA_DIR'] = Path('data')
app.config['DB_PATH'] = app.config['DATA_DIR'] / 'model_evals.db'

# Database connection
def get_db():
    db = sqlite3.connect(app.config['DB_PATH'], detect_types=sqlite3.PARSE_DECLTYPES)
    db.row_factory = sqlite3.Row
    return db

@app.route('/', methods=['GET', 'POST'])
def home():
    if request.method == 'POST':
        session['app'] = request.form['app']
        return redirect(url_for('home'))
    return render_template('home.html', app=session.get('app'))

@app.route('/load_data', methods=['GET', 'POST'])
def load_data():
    if 'app' not in session:
        return redirect(url_for('home'))

    files = [f for f in os.listdir(app.config['DATA_DIR']) if f.endswith(('.csv', '.ods', '.xlsx'))]

    if request.method == 'POST':
        selected_file = request.form.get('file')
        if selected_file:
            file_path = app.config['DATA_DIR'] / selected_file
            if file_path.exists():
                queries, headers = load_queries(file_path)
                available_prompts = get_available_prompts(session['app'])

                return render_template('select_prompt.html',
                                       app=session['app'],
                                       file=selected_file,
                                       prompts=available_prompts)
            else:
                flash("Selected file does not exist.", "error")

    return render_template('load_data.html', app=session['app'], files=files)

@app.route('/select_prompt', methods=['POST'])
def select_prompt():
    if 'app' not in session:
        return redirect(url_for('home'))

    selected_file = request.form.get('file')
    selected_prompt = request.form.get('prompt')

    if selected_file and selected_prompt:
        db = get_db()
        file_path = app.config['DATA_DIR'] / selected_file
        queries, headers = load_queries(file_path)

        try:
            load_data_func(db, file_path, session['app'], selected_prompt)
        except ValueError as e:
            flash(str(e), "error")
            return redirect(url_for('load_data'))

        flash("Data loaded successfully.", "success")
        return redirect(url_for('home'))

    return render_template('select_prompt.html', app=session['app'], file=selected_file, prompts=available_prompts)

@app.route('/responses', methods=['GET', 'POST'])
def responses():
    db = get_db()
    if request.method == 'POST':
        action = request.form['action']
        prompt_set_id = int(request.form['prompt_set'])
        model = request.form['model']

        if action == 'generate':
            gen_responses_func(db, prompt_set_id, model)
            flash("Responses generated successfully.", "success")
        elif action == 'evaluate':
            cur = db.execute("SELECT id FROM response_set WHERE response_set.prompt_set_id=? AND response_set.model=?", [prompt_set_id, model])
            response_set_id = cur.fetchone()['id']
            eval_model = "gemini/gemini-1.5-flash-latest"   # TODO: un-hardcode evaluating model
            gen_evals_func(db, eval_model, response_set_id, "make_sufficient_prompt")  # TODO: un-hardcode prompt type
            flash("Responses evaluated successfully.", "success")

        return redirect(url_for('responses'))

    # Get all prompt sets
    prompt_sets = db.execute("""
        SELECT prompt_set.id, prompt_set.created, prompt_set.query_src_file, prompt_set.prompt_func,
               COUNT(prompt.id) as prompt_count
        FROM prompt_set
        LEFT JOIN prompt ON prompt_set.id = prompt.set_id
        GROUP BY prompt_set.id
        ORDER BY prompt_set.created
    """).fetchall()

    # Get existing response sets
    existing_responses = db.execute("""
        SELECT prompt_set_id, model
        FROM response_set
    """).fetchall()

    # Get existing evaluations
    existing_evaluations = db.execute("""
        SELECT DISTINCT response_set.prompt_set_id, response_set.model
        FROM eval_set
        JOIN response_set ON eval_set.response_set_id = response_set.id
    """).fetchall()

    # Create sets of tuples (prompt_set_id, model) for easy lookup
    existing_responses_set = set((r['prompt_set_id'], r['model']) for r in existing_responses)
    existing_evaluations_set = set((e['prompt_set_id'], e['model']) for e in existing_evaluations)

    # Get all models
    models = sorted({r['model'] for r in existing_responses + existing_evaluations})

    return render_template('responses.html',
                           prompt_sets=prompt_sets,
                           models=models,
                           existing_responses=existing_responses_set,
                           existing_evaluations=existing_evaluations_set)

def get_response_set_id(db, prompt_set_id, model):
    result = db.execute("""
        SELECT id
        FROM response_set
        WHERE prompt_set_id = ? AND model = ?
    """, [prompt_set_id, model]).fetchone()
    return result['id'] if result else None


@app.route('/view_results', methods=['GET'])
def view_results():
    db = get_db()
    eval_sets = db.execute("""
        SELECT eval_set.*, response_set.model AS response_model, prompt_set.prompt_func, prompt_set.created AS prompt_created
        FROM eval_set
        JOIN response_set ON response_set.id=eval_set.response_set_id
        JOIN prompt_set ON prompt_set.id=response_set.prompt_set_id
        ORDER BY prompt_set.prompt_func, response_set.model, prompt_set.created
    """).fetchall()

    results = []
    for eval_set in eval_sets:
        eval_rows = db.execute("""
            SELECT eval.evaluation
            FROM eval
            WHERE eval.set_id = ?
        """, [eval_set['id']]).fetchall()

        evaluations = [json.loads(row['evaluation']) for row in eval_rows]

        ok_total = sum('OK.' in eval_dict for eval_dict in evaluations)
        ok_true = sum(eval_dict.get('OK.') == True for eval_dict in evaluations)
        ok_false = ok_total - ok_true

        other_total = sum(len([k for k in eval_dict.keys() if k != 'OK.']) for eval_dict in evaluations)
        other_true = sum(sum(v == True for k, v in eval_dict.items() if k != 'OK.') for eval_dict in evaluations)
        other_false = other_total - other_true

        results.append({
            'id': eval_set['id'],
            'prompt_func': eval_set['prompt_func'],
            'prompt_created': eval_set['prompt_created'],
            'response_model': eval_set['response_model'],
            'eval_model': eval_set['model'],
            'ok_true': ok_true,
            'ok_false': ok_false,
            'other_true': other_true,
            'other_false': other_false
        })

    return render_template('view_results.html', results=results)

@app.template_filter('percentage')
def percentage_filter(value, total):
    return f"{(value / total * 100):.1f}%" if total > 0 else "N/A"

@app.route('/view_false_responses/<int:eval_set_id>')
def view_false_responses(eval_set_id):
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
        SELECT response.text, eval.evaluation, prompt.model_response
        FROM eval
        JOIN response ON response.id = eval.response_id
        JOIN prompt ON prompt.id = response.prompt_id
        WHERE eval.set_id = ? AND eval.evaluation LIKE '%false%'
    """, [eval_set_id]).fetchall()

    false_responses = [
        {
            'text': row['text'],
            'evaluation': json.loads(row['evaluation']),
            'model_response': row['model_response']
        }
        for row in false_responses
    ]

    return render_template('view_false_responses.html', eval_set=eval_set, false_responses=false_responses)
