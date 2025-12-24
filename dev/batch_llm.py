#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2025 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

import argparse
import asyncio
import csv
import sys
from pathlib import Path
from typing import Any

import litellm
from loaders import load_data, test_and_report_model
from tqdm.auto import tqdm

# Hardcoded template - edit as needed
PROMPT_TEMPLATE = "Please review the following message from a tutor to a student, and determine whether the tutor has written any **solution code** for the student.  That is, has the tutor written code that directly solves the student's problem?  Reply with either \"Yes\" followed by a one-sentence explanation of that answer or simply \"No\" with no explanation.\n\n{value}"


async def get_completion(
    model: str,
    prompt: str,
    reasoning_effort: str | None = None,
    verbosity: str | None = None,
) -> str:
    """Fetch a single completion from the LLM."""
    response = await litellm.acompletion(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        max_completion_tokens=10000,
        reasoning_effort=reasoning_effort,
        verbosity=verbosity,
        allowed_openai_params=['reasoning_effort', 'verbosity'],
    )
    return response.choices[0].message.content.strip()


async def process_batches(rows: list[dict[str, Any]], args: argparse.Namespace) -> list[dict[str, Any]]:
    total_errors = 0

    # Process in batches
    for i in tqdm(range(0, len(rows), args.batch_size), desc="Processing batches", ncols=60):
        batch_indices = range(i, min(i + args.batch_size, len(rows)))
        tasks = []

        for idx in batch_indices:
            row = rows[idx]
            assert args.column in row
            prompt = PROMPT_TEMPLATE.format(value=row[args.column])
            tasks.append(get_completion(args.model, prompt, args.reasoning_effort, args.verbosity))

        # Run batch concurrently
        batch_results = await asyncio.gather(*tasks, return_exceptions=True)

        for idx, res in zip(batch_indices, batch_results):
            row = rows[idx]
            if isinstance(res, Exception):
                error_msg = f"[Error: {res}]"
                row['llm_response'] = error_msg
                total_errors += 1
                tqdm.write(f"Error on row {idx}: {error_msg}")
            else:
                row['llm_response'] = res

            if total_errors >= 5:
                tqdm.write("\nTerminating: 5 total errors occurred.")
                return rows

    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Process a spreadsheet column through an LLM.")
    parser.add_argument("input_file", type=Path, help="Path to input .csv, .ods, or .xlsx")
    parser.add_argument("output_file", type=Path, help="Path to save the output .csv")
    parser.add_argument("--column", type=str, required=True, help="The column name to use as input")
    parser.add_argument("--model", type=str, required=True, help="LLM model to use")
    parser.add_argument("--batch-size", type=int, default=1, help="Number of concurrent requests")
    parser.add_argument(
        '--reasoning-effort',
        type=str,
        choices=['none', 'minimal', 'low', 'medium', 'high'],
        required=False,
        help="The 'reasoning effort' parameter (OpenAI or compatible only).",
    )
    parser.add_argument(
        '--verbosity',
        type=str,
        choices=['low', 'medium', 'high'],
        required=False,
        help="The 'verbosity' parameter (OpenAI or compatible only).",
    )

    args = parser.parse_args()

    test_and_report_model(args.model, args.reasoning_effort, args.verbosity)

    rows, headers = load_data(args.input_file)

    if args.column not in headers:
        print(f"Error: Column '{args.column}' not found in headers: {headers}")
        sys.exit(1)

    # Run async processing
    print(f"Processing {len(rows)} rows in batches of {args.batch_size}...")
    try:
        asyncio.run(process_batches(rows, args))
    except KeyboardInterrupt:
        print("\nInterrupted by user. Saving partial results...")

    # Write output
    output_headers = [*list(headers), "llm_response"]
    with args.output_file.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=output_headers)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Done. Results saved to {args.output_file}")


if __name__ == "__main__":
    main()
