# Learning Contexts — Specification

Status: specification revised after a sixth design review; the config JSON
transform was simplified and the former Phases 1 and 4 were merged into one
atomic change in a follow-up review.  The per-class context-string split was
dropped, and the remaining migration, test, and Starburst-verification
questions are resolved below.  Phases 0 through 7 are complete.

## Overview

`code_contexts` becomes `learning_contexts`: a general-purpose context
component for any course.  Each context has a short name, visible details, and
a hidden instructions area containing general guidance and an avoid list.
CodeHelp and Starburst use the same component; app-specific guidance lives in
each app's documentation.

Persisted identifiers remain stable:

- component registry name: `contexts`
- config table name: `context`
- config item type: `context`
- config table labels: singular `context`, plural `contexts` (the instructor
  config page header remains **Contexts**; this is separate from the
  component's display name)
- instructor URLs and share-link keys are unchanged
- component display name: **Learning Contexts**
- Python package: `learning_contexts`
- component is always enabled

CodeHelp registers `learning_contexts` before `code_queries` for clarity.
There is no schema or foreign-key ordering dependency between the two
components.  `learning_contexts` no longer defines a schema file; the
`context_strings` dedup table is owned by `code_queries` (see below).

## Context data model

```json
{
  "name": "Python",
  "details": "- Python\n- Flask\n\nStudents are learning functional programming, with an emphasis on recursion.",
  "guidance": "Assume a beginner level and use Socratic questioning.",
  "avoid": "eval()\nzfill()"
}
```

`ContextConfig` contains `name`, `details`, `guidance`, and `avoid`.

- `name` — required; the short label students use to choose the context.
- `details` — markdown, default empty; shown to students and sent to the LLM.
- `guidance` — markdown, default empty; sent to the LLM but not shown to students.
- `avoid` — plain text, one entry per line, default empty; sent to the LLM as a
  negative instruction and not shown to students.

The fields are intentionally few and role-based.  Instructors can use markdown
headings, lists, and paragraphs inside `details` or `guidance` to organize
arbitrary content.

All three content keys are always present in stored JSON for instructor-
authored rows, including when empty (`details`, `guidance`, and `avoid` default
to `""`).  `ContextConfig.to_json()` serializes every field, so editing a
context normalizes its stored shape.  There is no "omit empty keys"
serialization.  Readers treat a missing content key as `""` for compatibility
with old or future rows.  `config = '{}'` is the erased shape written during
class deletion; a non-anonymized `{}` row is a legacy empty config and is
normalized by the migration.  See **Privacy**.

## Defaults and guidance

A new context starts with every content field empty.  The field labels and help
text provide the default guidance, so there is no pre-filled content for
instructors to remove.

The component's help text is subject-neutral and links to the application's
`contexts` documentation when that page exists.  Each application's
documentation provides examples and suggestions specific to that application.

## LLM prompt

```text
Context name: <name>Python</name>
Details: <details>
- Python
- Flask

Students are learning functional programming, with an emphasis on recursion.
</details>

General guidance: <guidance>Assume a beginner level and use Socratic questioning.</guidance>

Terms and concepts to avoid (do not mention these terms or concepts in your response at all): <avoid>eval(); zfill()</avoid>
```

- Empty fields are omitted.  A field containing only whitespace is treated as
  empty.
- If every content field is empty or whitespace-only, the prompt contains only
  the context name.
- `details` and `guidance` are included verbatim as markdown; they are not
  rendered to HTML for the prompt.
- The stored `avoid` text is newline-separated; the prompt renders it as a
  `; `-joined list.  Blank lines and surrounding whitespace are ignored.
- Content is included in the fixed order: details, guidance, avoid.

The previous prompt format is not preserved exactly; semantic equivalence is
accepted.

## Student-facing description

Only `details` is shown to students.  `desc_html()` renders `details` through
the application's markdown filter and returns that HTML directly.  It does not
add a "Details:" heading or any other label; the context chooser already labels
the selected item, and the description panel should contain only the
instructor's content.  `guidance` and `avoid` are never shown to students.  If
`details` is empty or contains only whitespace, `desc_html()` returns an empty
string and the context chooser shows only the context name.

## Instructor UI

The context edit form provides:

- **Name** — required.
- **Details** — markdown; shown to students.
- **Additional instructions (not shown to students)** — a single area
  containing:
  - **General guidance** — optional markdown.
  - **Terms and concepts to avoid** — plain text, one entry per line.

The two hidden inputs remain separate in the data model and prompt, but are
grouped visually so instructors see one "hidden instructions" concept.

Help text is generic and subject-neutral.

## Context strings

`context_strings` remains a global deduplication table, owned by the
`code_queries` component:

```sql
CREATE TABLE context_strings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ctx_str TEXT NOT NULL UNIQUE
);
```

- The table shape is **unchanged** from the current pre-refactor schema.  It
  has no `class_id`, no per-class uniqueness, and no expression index.
- `record_context_string(ctx_str)` lives in `code_queries` and has the same
  signature as today.  It records the full rendered context text and returns
  the existing row ID when the same string already exists.
- `code_queries.context_string_id` keeps its existing foreign key to
  `context_strings(id)`.
- Historical context strings are not re-rendered after the refactor.
- Deduplication is global across classes.  A string may be shared by queries
  from multiple classes.
- The table is created only where `code_queries` is registered (currently
  CodeHelp).  Starburst does not register `code_queries` and therefore has no
  `context_strings` table.
- `learning_contexts` no longer has a schema file and no longer owns or touches
  `context_strings`.

### Why keep the dedup table

Production data shows the table earning its keep: roughly 41,000
`code_queries` rows reference about 251 distinct context strings totaling about
500,000 characters (about 2,000 characters per string).  Inlining the rendered
prompt on every query would store roughly 82,000,000 characters, or about
80 MB, instead of about 500 KB.  That is a meaningful saving, and it grows with
query volume.

The table is a storage cache, not a privacy boundary.  It does not need class
attribution.

### Why there is no per-class split

The previous design duplicated strings per class so that deleting one class
could remove its row even when another class used the same text.  That adds a
large amount of machinery for little practical benefit:

- If two classes use the identical string, deleting one class's row leaves the
  other class's identical row.  The text remains in the system either way.
- Duplicating per class does not remove the content from the other class; that
  class legitimately has its own copy.
- Orphan cleanup (below) removes a string once no query references it, which is
  the same eventual outcome.
- The current production behavior already keeps shared strings.  This
  specification keeps that behavior and documents it rather than rebuilding the
  data model.

If a future requirement demands strict per-class row attribution (for example,
"delete class A's row even when class B references identical text"), that is a
separate design change.  It would require per-class duplication and a data
migration; it would still not remove the text from class B's own copy.

## Migration

The refactor requires **one** data migration:

| Migration | Runs in | Responsibility |
|---|---|---|
| `learning_contexts` component migration | Every application that registers `learning_contexts` (CodeHelp and Starburst) | Transform context config JSON |

File:

- `src/components/learning_contexts/migrations/20261125--learning-contexts--refactor.sql`

The filename must sort after
`src/gened/migrations/20260605--unify-contexts-and-tutors.sql`.  That gened
migration creates and populates `config_items` on databases that predate the
unified config table.  Fresh databases already have `config_items` from
`gened/schema_common.sql`, but upgrades do not.  The `20261125` timestamp
satisfies this.  There is no ordering constraint between `learning_contexts`
and `code_queries`.

There is **no** `context_strings` migration:

- The table shape and its rows do not change.
- Existing CodeHelp databases already have the table.
- Fresh CodeHelp databases create it from `code_queries/schema.sql`.
- Starburst never creates it because it does not register `code_queries`.
- Moving ownership from `learning_contexts` to `code_queries` is a schema-file
  move, not a data migration.
- Therefore there is no table rebuild, no composite `(old_id, class_id) →
  new_id` mapping, no unreferenced-string preservation step, no index
  creation, and no ordering requirement between the `learning_contexts` and
  `code_queries` components.

### `learning_contexts` migration: config JSON transform

Transform `config_items.config` for `item_type='context'`, except erased rows:

- Skip erased rows only: `config = '{}'` and `name LIKE '[deleted]%'`.  These
  are anonymized rows written by class deletion and are covered by the
  **Privacy** exception.  The migration must not rewrite them.  A `{}` row with
  a normal name is a legacy real-but-unconfigured context and must be
  transformed.
- Normalize line endings in old `tools` and `details` to `\n` and trim
  surrounding whitespace from each field.  Do not split either field into
  lines.
- Render old `tools` as a single `; `-joined line.  If `tools` is nonempty, the
  combined `details` starts with `**Environment and tools:** ` followed by that
  line.
- Old `details` is appended after a blank line when both fields are nonempty.
- Resulting format (normal case):

  ```markdown
  **Environment and tools:** Python; Flask

  Students are learning functional programming, with an emphasis on recursion.
  ```

- If `tools` is empty after trimming, use the trimmed old `details` with no
  heading.
- If `details` is empty after trimming, omit the trailing blank block.
- If both are empty, `details` is `""`.
- Preserve old `avoid` text as-is; the prompt formatter handles CRLF and blank
  lines.
- Ensure the JSON `name` key is present: preserve it when present, otherwise use
  `config_items.name`.
- Always write all three content keys for non-anonymized rows, including empty
  strings: `details`, `guidance`, and `avoid`.  There is no "omit empty fields"
  variant.  Use `COALESCE(..., '')` so missing or NULL values become empty
  strings, never JSON null.
- Empty non-anonymized old configs become `name` (from the column),
  `details: ""`, `guidance: ""`, `avoid: ""`.

Implementation notes:

- This transform is intentionally simple.  It does not attempt to preserve
  markdown indentation, remove empty lines, or clean up whitespace within old
  `tools` content.  A few stray spaces or extra `; ` separators in legacy
  content are acceptable.
- Normalize line endings with
  `replace(replace(x, char(13,10), char(10)), char(13), char(10))`.  Use
  `trim(x, ' ' || char(9) || char(10) || char(13))` to trim surrounding
  whitespace.  For old `tools`, then use
  `replace(trimmed_tools, char(10), '; ')` to join lines.
- Compute the new `details` with a `CASE` expression:
  - both empty: `''`
  - tools empty: trimmed old `details`
  - details empty: `'**Environment and tools:** ' || joined_tools`
  - both nonempty:
    `'**Environment and tools:** ' || joined_tools || char(10) || char(10) || trimmed_details`
- No recursive CTE or line splitting is needed.
- Skip only erased rows:
  `AND NOT (config = '{}' AND name LIKE '[deleted]%')`.
- Use
  `json_set(config, '$.name', COALESCE(json_extract(config, '$.name'), name), '$.details', ..., '$.guidance', COALESCE(json_extract(config, '$.guidance'), ''), '$.avoid', COALESCE(json_extract(config, '$.avoid'), ''))`
  and `json_remove(config, '$.tools')`, with `COALESCE(..., '')` on `details`,
  `guidance`, and `avoid`.  Preserve any other keys.
- Wrap the script in `BEGIN;`/`COMMIT;`.
- The migration must run before the new code serves requests.  `from_row()`
  ignores unknown `tools` content and treats missing content keys as empty, so
  until the migration runs, old `tools` content is silently dropped from
  prompts and student descriptions.  There is no runtime guard; deployment must
  run `flask migrate` first (see **P2.5** and the **Verification commands**).

### Fresh databases

- `flask initdb` uses `code_queries/schema.sql`, which creates
  `context_strings` and then `code_queries` with its foreign key.
- `learning_contexts` has no schema file and creates no tables.
- `init_db` marks all migrations as applied.
- Starburst has no `context_strings` table and no `code_queries` table.

## Privacy

Contexts are class data.  User deletion requires no context-specific handling.

On class deletion:

- `ContextsDeletionHandler` anonymizes `context` config items only:
  - `name = '[deleted]' || id`
  - `config = '{}'`
  - It no longer reads or writes `code_queries` or `context_strings`, and it
    does not toggle `PRAGMA foreign_keys`.
- If `code_queries` is registered, `QueriesDeletionHandler.delete_class_data`
  nulls `context_string_id` for the class's queries, then deletes context
  strings that no query references:
  ```sql
  DELETE FROM context_strings
  WHERE NOT EXISTS (
      SELECT 1
      FROM code_queries AS q
      WHERE q.context_string_id = context_strings.id
  );
  ```
- The nulling must happen before the delete so the foreign key is never
  violated.  No `PRAGMA foreign_keys` change is needed.
- Handler order is irrelevant: the contexts handler and the queries handler
  touch disjoint data.
- A context string also used by another class is left in place, because the
  other class's queries still reference it.  This is intentional: the text is
  also the other class's data, and it cannot be deleted without corrupting that
  class's history.  It is removed later when the last reference goes away.
- A context string referenced only by a query with no class (`role_id IS NULL`)
  is left in place; orphan cleanup only removes strings with zero references.

On user deletion:

- `QueriesDeletionHandler.delete_user_data` already nulls
  `context_string_id` for the user's queries.  It then deletes context strings
  that no query references.
- `TutorsDeletionHandler` continues to clear `chat_json`, which holds the full
  rendered system prompt for chats.

Anonymized context configs use `config = '{}'` and are the one documented
exception to the "all content keys are present" invariant.  The row is not a
usable context: its class is deleted or disabled, and `from_row()` fills
defaults if it is ever loaded.  The refactor migration skips only erased rows
(`config = '{}'` and `name LIKE '[deleted]%'`), so historical and newly
anonymized rows keep that shape.  Non-anonymized `{}` rows are legacy empty
configs and are normalized to the full shape.

## Documentation

- **CodeHelp:** rewrite `docs/contexts.md` for the two visible/hidden areas,
  with CS examples for details, general guidance, and terms and concepts to
  avoid.
- **Starburst:** add `docs/contexts.md` with general examples for details,
  general guidance, and terms and concepts to avoid.
- Component help text is generic and subject-neutral.
- Keep the existing docs-link behavior: show the link when `contexts` is
  present in `docs_pages`.

## Starburst integration

- Register `learning_contexts` in Starburst.
- Inquiry chats gain context selection automatically.
- `context_help_form` is hidden because `code_queries` is absent;
  `context_inquiry_chat` remains available.
- There is no `context_strings` table; inquiry chats already store the full
  system prompt inside `chats.chat_json`, so historical context text is
  retained there.
- The component remains always enabled.
- Starburst behavior is verified manually; this change does not add an
  automated Starburst app fixture.  See **P6.2** and **P7.5**.

## Implementation Plan

This section is the working checklist for implementing the spec.  It is
designed to be edited in place: check tasks off, add notes beneath each phase,
and append entries to the running log.  Task IDs are stable references for
commits, PR comments, and review discussions.

### How to use this plan

- Mark a task done by changing `- [ ]` to `- [x]`.
- Update the phase's **Status** line as work starts and finishes.
- Add notes under the phase's **Notes** heading.  Prefer dated notes when the
  history matters.
- Record decisions, surprises, and follow-ups in the **Running log** at the
  bottom.
- If scope changes, add a task rather than silently expanding an existing one.

**Status legend:** ☐ Not started · ◐ In progress · ☑ Done · ⚠ Blocked · ⊘ Skipped

### Progress summary

| Phase | Status | Notes |
|---|---|---|
| 0. Baseline and decisions | ☑ | Baseline clean; scratch DB copies recorded.  No production-like CodeHelp copy was available, so the dev DB was used and noted. |
| 1. Rename, registration, and data layer | ☑ | Atomic data-layer move, package rename, Starburst registration; 246 tests pass. |
| 2. Model and prompt | ☑ | New role-based model and prompt; tests and shared fixtures updated.  `pytest` 253 passed; mypy/ruff/djlint clean. |
| 3. Instructor UI | ☑ | Form groups visible details separately from hidden guidance/avoid; help text subject-neutral; UI tests added.  `pytest` 255 passed; mypy/ruff/djlint clean. |
| 4. Context strings and data layer | ⊘ | Merged into Phase 1. |
| 5. Migration | ☑ | Config JSON transform migration and regression tests added; exercised on the Phase 0 copies and a fresh CodeHelp DB.  `pytest` 258 passed; mypy/ruff/djlint clean. |
| 6. App integration and docs | ☑ | Starburst registration and manual checks confirmed; CodeHelp and Starburst context docs written; related CodeHelp docs updated. |
| 7. Verification and cleanup | ☑ | All checks clean; CodeHelp and Starburst smoke paths exercised on fresh scratch databases; only stale references are in the untracked `dev/lti_deep_linking.md` (out of scope). |

### Phase 0 — Baseline and decisions

**Status:** ☑ Done

- [x] **P0.1** Run the current checks on the starting commit and record the
  baseline: `pytest`, `mypy`, `ruff check`, `djlint src`.
- [x] **P0.2** Confirm the working branch and the single migration filename:
  `20261125--learning-contexts--refactor.sql`.  It must sort after
  `20260605--unify-contexts-and-tutors.sql`, which creates and populates
  `config_items` on pre-unification databases.  There is no ordering constraint
  between `learning_contexts` and `code_queries`.
- [x] **P0.3** Copy a production-like CodeHelp database (with roughly 41,000
  `context_string_id` references and 251 `context_strings` rows) and a current
  pre-refactor Starburst database to a scratch location for migration testing.
  If a production copy is not available, use `instance/codehelp.db` but note
  that it is not representative of production context-string usage.  If the
  available Starburst database predates the current schema, bring it up to the
  current pre-refactor state first or create a fresh Starburst database with
  the current code.  Do not test migrations against `instance/`.
- [x] **P0.4** Record the pre-migration state of the copied databases:
  - `SELECT count(*), coalesce(sum(length(ctx_str)), 0) FROM context_strings;`
  - `SELECT count(*) FROM code_queries WHERE context_string_id IS NOT NULL;`
  - `SELECT count(*) FROM config_items WHERE item_type = 'context';`
  - `SELECT count(*) FROM config_items WHERE item_type = 'context' AND config = '{}';`
  - `SELECT count(*) FROM config_items WHERE item_type = 'context' AND config = '{}' AND name LIKE '[deleted]%';`
  - `SELECT count(*) FROM config_items WHERE item_type = 'context' AND config = '{}' AND name NOT LIKE '[deleted]%';`
  - `SELECT filename FROM migrations ORDER BY filename;`
  - `.schema context_strings`
- [x] **P0.5** Record the review decisions that constrain implementation:
  skip only erased `config = '{}'` rows (`name LIKE '[deleted]%'`); transform
  non-anonymized `{}` rows to `name` plus all three content keys; readers treat
  missing content keys as empty; use simple line-ending normalization, outer
  trimming, and `; ` joining of old `tools`; verify Starburst manually; do not
  add a runtime guard for old `tools` content (deployment must run the migration
  first).

**Notes:**

- 2026-11-25: Baseline on `main` at `32df2e5`:
  - `pytest -q`: 245 passed.
  - `mypy`: success, no issues in 95 source files.
  - `ruff check`: all checks passed.
  - `djlint src`: 0 errors across 45 files.
- 2026-11-25: Confirmed no `20261125--learning-contexts--refactor.sql`
  exists yet.  The new filename sorts after
  `20260605--unify-contexts-and-tutors.sql`; no ordering constraint with
  `code_queries`.
- 2026-11-25: No production-like CodeHelp copy (roughly 41,000 references /
  251 strings) was available, so the permitted fallback was used:
  `instance/codehelp.db` copied to
  `/tmp/opencode/learning_contexts_phase0/codehelp/codehelp.db`.  It is a dev
  database and is **not** representative of production context-string usage.
- 2026-11-25: `instance/starburst.db` predated the current schema (it still
  had the old `contexts` table and no `config_items`).  A copy at
  `/tmp/opencode/learning_contexts_phase0/starburst_upgraded/starburst.db`
  was brought to the current pre-refactor state with
  `FLASK_APP=starburst flask migrate --auto` (using an existing model
  shortname override because the old database lacked the `.env` model).  A
  second fresh Starburst database was created at
  `/tmp/opencode/learning_contexts_phase0/starburst_fresh/starburst.db`.
- 2026-11-25: Pre-migration CodeHelp copy state:
  - `context_strings`: 9 rows, 1,490 total characters.
  - `code_queries` with a context string: 28.
  - Context config items: 390.
  - Total empty `{}` contexts: 281 (280 with a normal name, 1 erased
    `[deleted]` row).
  - Migrations applied: 75; newest is
    `20261007--deprecate-gpt41nano.sql`.
  - `context_strings` schema is unchanged:
    `id INTEGER PRIMARY KEY AUTOINCREMENT`, `ctx_str TEXT NOT NULL UNIQUE`.
- 2026-11-25: Pre-migration Starburst copies:
  - Upgraded current-state copy: 64 migrations, no `contexts`,
    `context_strings`, or `code_queries` tables; `config_items` exists with 1
    empty context row (the migrated `Default` context).
  - Fresh copy: 64 migrations, no `contexts`, `context_strings`, or
    `code_queries` tables; `config_items` exists with 0 context rows.
- 2026-11-25: Decisions confirmed as written in P0.5, including
  deployment-only migration sequencing and manual Starburst verification.

### Phase 1 — Rename, registration, and data layer

**Status:** ☑ Done

This phase is one atomic change.  It combines the former Phase 1 and Phase 4
because the package rename, the `context_strings` schema/function move, and the
deletion-handler changes must not be deployed separately.  Doing the data-layer
moves first keeps the app and tests working throughout.

**1A — Data layer and deletion cleanup**

- [x] **P4.1** Move the `context_strings` DDL from
  `src/components/code_contexts/schema.sql` to `code_queries/schema.sql`:
  - keep the exact current shape:
    `id INTEGER PRIMARY KEY AUTOINCREMENT`, `ctx_str TEXT NOT NULL UNIQUE`
  - create the table before `code_queries` in the same schema file
  - if the schema file has `DROP TABLE` statements, drop `code_queries` before
    `context_strings` so the foreign key is never dangling
  - delete `src/components/code_contexts/schema.sql`
  - remove `schema_file="schema.sql"` from
    `src/components/code_contexts/__init__.py` now that the DDL has moved
- [x] **P4.2** Move `record_context_string(ctx_str)` from
  `src/components/code_contexts/data.py` to `code_queries/data.py`:
  - keep the signature and the
    `INSERT ... ON CONFLICT DO UPDATE SET id=id RETURNING id` pattern
  - update `code_queries/helper.py` and `tests/test_context_strings.py` to
    import it from `.data`
  - remove it from the `code_contexts` package exports
- [x] **P4.3** Simplify `ContextsDeletionHandler.delete_class_data()`:
  - keep the config-item anonymization (`name`, `config = '{}'`)
  - remove all `code_queries` and `context_strings` logic
  - remove the `PRAGMA foreign_keys` toggling
  - update the class docstring/comment to refer to `learning_contexts`
    (the package rename follows in P1)
- [x] **P4.4** Add orphan cleanup to `QueriesDeletionHandler`:
  - in `delete_user_data()`, after nulling `context_string_id`, delete context
    strings with no remaining query references
  - in `delete_class_data()`, after nulling `context_string_id` for the class's
    queries, delete context strings with no remaining query references
  - null before delete; do not toggle `PRAGMA foreign_keys`
  - P4.3 and P4.4 must land together: do not remove the old cleanup before the
    new cleanup exists
- [x] **P4.5** Verify `record_query()` in `code_queries/helper.py` still calls
  `record_context_string(context_str)` with no class argument, and that
  `code_queries.context_string_id` is populated exactly as before.

**1B — Package rename and registration**

- [x] **P1.1** Move the package:
  `src/components/code_contexts` → `src/components/learning_contexts`.
- [x] **P1.2** Update `learning_contexts/__init__.py`:
  - `package=__package__`
  - `name="contexts"` (unchanged)
  - `Blueprint('contexts', ...)` name unchanged
  - `display_name="Learning Contexts"`
  - subject-neutral component description
  - confirm `schema_file` is absent (P4.1 removed it after moving the DDL)
  - keep `migrations_dir="migrations"`
  - keep `always_enabled=True`
  - confirm `record_context_string` is absent from imports and `__all__`
    (P4.2 moved it to `code_queries`)
- [x] **P1.3** Update remaining consumer imports of the package:
  - `src/components/code_queries/helper.py`
  - `src/components/tutors/chat.py`
  - `src/components/tutors/chat_helpers.py`
  - `tests/test_class_config.py`, `tests/test_contexts.py`,
    `tests/test_contexts_model.py`, `tests/test_privacy.py`
- [x] **P1.4** Update application factories:
  - `src/codehelp/__init__.py` (keep `learning_contexts` registered before
    `code_queries` for clarity; there is no schema dependency)
  - `src/starburst/__init__.py` (add the component; P4.3/P4.4 have already made
    deletion work without a `context_strings` table)
- [x] **P1.5** Grep for stale references: `code_contexts`, `Code Contexts`,
  `code_contexts component`, and the `tutor_new_form.html` comment.  Also
  check `dev/lti_deep_linking.md`; if that file is still untracked user work,
  note it as out of scope rather than editing it.
- [x] **P1.6** Smoke test imports and the instructor config page.

**1C — Tests and verification after the atomic change**

- [x] **P4.6** Update data-layer tests:
  - `tests/test_context_strings.py`: keep dedup coverage and the existing
    deletion expectations (class-only strings deleted, shared strings
    retained, classless-referenced strings retained); the cleanup now runs in
    `QueriesDeletionHandler` rather than `ContextsDeletionHandler`.
  - `tests/test_context_strings.py`: add a user-deletion case: a string
    referenced only by the deleted user's queries is removed; shared strings
    remain; the user's queries get `context_string_id = NULL`.
  - `tests/test_privacy.py`: config anonymization remains `{}`; class queries
    still get `context_string_id = NULL`; shared strings are retained
  - `tests/test_app_data.py`: no change expected (`context_string_id` is still
    a query column)
- [x] **P4.7** Verify Starburst manually: no `context_strings` table, no
  `code_queries` table, and class deletion still works (only config
  anonymization).  No automated Starburst fixture is added.

**Notes:**

- 2026-11-25: Moved `context_strings` DDL into `code_queries/schema.sql`
  (queries dropped before strings) and deleted the `learning_contexts` schema.
  `record_context_string()` now lives in `code_queries/data.py`.
- 2026-11-25: `ContextsDeletionHandler` now only anonymizes config items.
  `QueriesDeletionHandler` nulls `context_string_id` and then deletes
  unreferenced strings for both user and class deletion.  No foreign-key
  pragma toggling remains.
- 2026-11-25: Renamed the package to `learning_contexts`, updated consumers and
  tests, and registered the component in Starburst.  `dev/lti_deep_linking.md`
  is still untracked user work and was left unchanged.
- 2026-11-25: Added the user-deletion context-string test and a shared-string
  retention assertion for class deletion.  `pytest` passes (246 tests), `mypy`
  passes, `ruff` is clean, and `djlint` reports no errors.
- 2026-11-25: Manual Starburst check against the Phase 0 upgraded copy: no
  `context_strings` or `code_queries` tables; deleting class 1 anonymized its
  context row to `[deleted]1` / `{}`.  A fresh Starburst `initdb` also created
  neither table.

### Phase 2 — Model and prompt

**Status:** ☑ Done

- [x] **P2.1** Rewrite `ContextConfig` in `model.py`:
  - `details: str = ''`
  - `guidance: str = ''`
  - `avoid: str = ''`
  - remove `tools`
  - update `from_request_form()` to read `details`, `guidance`, `avoid`
  - keep `name` serialized by the existing `ConfigItem.to_json()`
  - always serialize all three content keys, including empty strings
- [x] **P2.2** Rewrite `prompt_str()`:
  - return just `name` when all content fields are empty or whitespace-only
  - render `details` (markdown) first
  - render `guidance` second
  - render `avoid` last with the fixed negative preamble
  - retain `_list_fmt()` for `avoid`, but ignore blank lines and surrounding
    whitespace
  - omit empty/whitespace-only fields
- [x] **P2.3** Rewrite `desc_html()` to render only `details` as markdown,
  with no added "Details:" heading.  `guidance` and `avoid` must never appear
  in student-facing HTML.  Return `""` when `details` is empty or
  whitespace-only.
- [x] **P2.4** Update `tests/test_contexts_model.py` for the new fields,
  prompt structure, and student description.
- [x] **P2.5** Document the `from_row()` behavior: `msgspec` ignores unknown
  fields and treats missing content keys as empty, so old JSON loads but
  silently drops `tools`; the migration must run before any request reads
  contexts.  Do not add a runtime guard.  Add model tests proving old-style JSON
  and `{}`/missing-field JSON load with defaults, so the deployment risk is
  explicit and covered.
- [x] **P2.6** Update shared test fixtures to the new config shape:
  `tests/test_data.sql` and the inline JSON in `tests/test_class_config.py`
  and `tests/test_lti.py`.  Include `name` in each real config, keep `guidance`
  empty, and move old `tools` content into `details` using the simplified
  migrated format from the migration section (`**Environment and tools:**
  Python2`, a blank line, then `details2`) so tests reflect production data.
  Update
  `tests/test_class_config.py` assertions that read `ctx_item.tools`.  Keep the
  `context_strings` seed rows in `tests/test_data.sql` unchanged (the table is
  global).  Migration regression tests must use a separate old-style fixture,
  not the updated shared data.
- [x] **P2.7** Update integration test prompt expectations for the new prompt
  labels and migrated fixtures:
  - `tests/test_helper.py`: update the prompt-label assertion to
    `Terms and concepts to avoid` and the test name/docstring that refer to the
    old prompt.  If the migrated fixture includes the
    `**Environment and tools:**` label in `details`, the corresponding
    assertion remains valid.
  - `tests/test_tutors.py`: update the prompt-label assertion from
    `Keywords and concepts to avoid` to `Terms and concepts to avoid`.

**Notes:**

- 2026-11-25: Replaced `tools` with `details`, `guidance`, and `avoid` in
  `ContextConfig`; `to_json()` now emits all three content keys (including
  empty strings).  `prompt_str()` omits blank/whitespace-only fields, joins
  nonblank `avoid` lines with `; `, and returns just the name when all content
  is empty.  `desc_html()` renders only `details` through the markdown filter
  with no added heading.
- 2026-11-25: Added a model module docstring documenting that `msgspec` drops
  legacy `tools` content and that the migration must run before serving.  Added
  `from_row()` tests for old-style `tools` JSON, `{}`, and missing content keys,
  plus prompt/description coverage for whitespace-only fields.
- 2026-11-25: Updated `tests/test_data.sql`, `tests/test_class_config.py`, and
  `tests/test_lti.py` to the new JSON shape, moving legacy `tools` content into
  `details` as `**Environment and tools:** ...`.  Updated prompt-label
  assertions in `tests/test_helper.py` and `tests/test_tutors.py`.
- 2026-11-25: Because the model no longer accepts `tools`, the create/update
  expectations in `tests/test_contexts.py` were updated now (otherwise they
  would fail); the remaining form/UI assertions for that file stay in Phase 3
  with the template rewrite.
- 2026-11-25: `pytest` 253 passed; `mypy` clean in 95 files; `ruff check`
  passed; `djlint src` found 0 errors.

### Phase 3 — Instructor UI

**Status:** ☑ Done

- [x] **P3.1** Rewrite `templates/context_edit_form.html`:
  - Name input
  - Details textarea (markdown; shown to students)
  - "Additional instructions (not shown to students)" group containing:
    - General guidance textarea (markdown)
    - Terms and concepts to avoid textarea (plain text, one per line)
  - preserve the existing create/update form actions and Bulma structure
- [x] **P3.2** Keep help text generic and subject-neutral.  Mention which
  fields are shown to students and which are not.
- [x] **P3.3** Update `config_table.py` help text.  Keep
  `ConfigTable.name='context'`, the singular/plural labels `context`/`contexts`
  (so the instructor page header stays **Contexts**), the existing
  `docs_pages` link behavior, and share-link keys unchanged.
- [x] **P3.4** Verify `context_chooser.html` still renders correctly when
  `details` is empty or whitespace-only (only the context name should appear,
  with no empty description panel).
- [x] **P3.5** Update tests for the new fields and student description:
  - `tests/test_contexts.py`: new form fields; create/update expected JSON
    (remove `tools`, add `guidance`); edit view; `desc_html()` no longer adding
    a "Details:" heading.
  - `tests/test_class_config.py`: `test_get_item_by_name_returns_context`
    assertions on `tools`/`details`/`avoid`; any inline old-shape JSON.
  - Add a whitespace-only `details` case for the empty-description behavior.
- [x] **P3.6** Run `djlint src` and inspect the result.

**Notes:**

- 2026-11-25: Rewrote the edit form with Name, Details (visible to students),
  and a bordered "Additional instructions (not shown to students)" group
  containing General guidance and Terms and concepts to avoid.  Removed the
  legacy `tools` textarea and reworded all help text to be subject-neutral.
- 2026-11-25: Updated the config table help text to describe contexts in
  general terms rather than languages/libraries, keeping the `context` table
  name, `context`/`contexts` labels, docs link, and share-link keys unchanged.
- 2026-11-25: Confirmed `context_chooser.html` already hides the description
  panel when `desc_html()` returns an empty string (its `x-show` guards on a
  truthy description); added an integration test for whitespace-only `details`.
- 2026-11-25: Updated `tests/test_contexts.py` for the new fields and edit-view
  values, and added a whitespace-only description test to `tests/test_helper.py`.
  `pytest` 255 passed; mypy clean; ruff clean; `djlint src` 0 errors.

### Phase 4 — Context strings and data layer

**Status:** ⊘ Merged into Phase 1

All former Phase 4 tasks (P4.1–P4.7) are now part of **Phase 1 — Rename,
registration, and data layer**, in dependency order.  Phase 1 is one atomic
change; do not deploy the rename or Starburst registration without the schema,
function, and deletion-handler moves.

**Notes:**

- 

### Phase 5 — Migration

**Status:** ☑ Done

- [x] **P5.1** Add the `learning_contexts` migration:
  `src/components/learning_contexts/migrations/20261125--learning-contexts--refactor.sql`.
  - Transform `config_items.config` for `item_type='context'`, skipping only
    erased rows (`config = '{}'` and `name LIKE '[deleted]%'`):
    - normalize line endings and trim surrounding whitespace in old `tools`
      and `details`; do not split lines
    - join old `tools` lines with `; ` and prefix
      `**Environment and tools:** ` when nonempty
    - old `tools` + `details` → new `details`, using the simplified format above
    - old `avoid` → new `avoid`
    - ensure `name` is present, using `config_items.name` when absent
    - ensure `guidance` is present, defaulting to empty
    - handle missing/NULL keys with `COALESCE(..., '')`
    - always write all three content keys for transformed rows, including
      empty strings
  - Wrap the script in `BEGIN;`/`COMMIT;`.
  - Do **not** create, alter, or index `context_strings`.
- [x] **P5.2** Confirm there is no new `code_queries` migration and no ordering
  requirement between `learning_contexts` and `code_queries`.  Confirm the new
  migration sorts after `20260605--unify-contexts-and-tutors.sql`; that is the
  only filename-ordering constraint.  The only outstanding migration is the
  config transform.
- [x] **P5.3** Add CodeHelp migration regression tests (for example
  `tests/test_migrations.py`):
  - Build a CodeHelp database with old-style context configs (`tools`,
    `details`, `avoid`) and existing `context_strings`/`code_queries` rows.
    One convenient approach: create a dedicated temporary instance/application,
    call `init_db`, insert the fixtures, then delete the new migration's row
    from `migrations` so the migration is pending.  Use a dedicated old-style
    fixture; do not rely on the updated `tests/test_data.sql`.
  - Run only the `learning_contexts` migration.  Call `_do_migration()`
    directly for the new migration, or run `flask migrate --auto` after
    confirming it is the only pending migration.  Assert that
    `20260605--unify-contexts-and-tutors.sql` is already applied.
  - Assert the transformed config JSON for: both fields, tools only, details
    only, both fields empty with empty keys, CRLF, missing keys, preserved
    `name`, and preserved `avoid`.  Assert that multiple old `tools` lines are
    joined with `; `.  Per-line whitespace and indentation are intentionally
    not tested because the transform does not promise to preserve them.
  - Assert a non-anonymized `{}` row becomes `name` plus all three empty content
    keys, and a row without a JSON `name` gets the column name.
  - Assert erased rows (`config = '{}'` and `name LIKE '[deleted]%'`) are
    unchanged.
  - Assert `context_strings` rows, IDs, and total length are unchanged, and
    `code_queries.context_string_id` values still join correctly.
  - Starburst migration behavior is verified manually against the Phase 0 copy
    (P5.4), not in this automated test module.
- [x] **P5.4** Test against the Phase 0 database copies:
  - Production-like CodeHelp DB: pre/post `context_strings` count (251), total
    length (~500,000), and `code_queries` count with a context string (about
    41,000) must be unchanged.
  - Spot-check transformed config JSON: non-anonymized `{}` rows gain `name`
    and empty content keys; erased `{}` rows are unchanged.
  - Current Starburst DB: a current pre-refactor database may contain legacy
    context rows and must normalize them; a fresh Starburst database has no
    context rows.  In either case, it must have no `context_strings` and no
    `code_queries` table.
- [x] **P5.5** Test the fresh-database path:
  - `flask initdb` uses the updated `code_queries/schema.sql`, not the
    migration.
  - Confirm `context_strings` has the unchanged shape and the `ctx_str` unique
    constraint.
  - Confirm `learning_contexts` creates no table.
  - Confirm all migrations are marked applied.
  - Starburst's fresh-database path is covered by the P6.2 manual checklist.
- [x] **P5.6** Run `flask migrate --auto` on the Phase 0 copies to exercise the
  real migration command.  Set the app (`FLASK_APP=codehelp` or
  `FLASK_APP=starburst`), `FLASK_INSTANCE_PATH`, and the required environment
  variables before running; use the copied database paths, not `instance/`.

**Notes:**

- 2026-11-25: Added
  `src/components/learning_contexts/migrations/20261125--learning-contexts--refactor.sql`.
  It normalizes CRLF/CR to LF, trims surrounding whitespace, joins old `tools`
  lines with `; `, folds them into `details`, removes `$.tools`, and writes
  `name`, `details`, `guidance`, and `avoid` for every non-erased context.
  Erased rows (`config = '{}'` and a `[deleted]` name) are skipped.
- 2026-11-25: Added `tests/test_migrations.py`, which builds a dedicated
  old-style CodeHelp fixture after `init_db`, deletes the new migration row to
  make it pending, and applies it through `flask migrate --auto`.  Coverage
  includes both/tools-only/details-only/empty, CRLF, missing keys, non-
  anonymized `{}`, column-name fallback for a missing JSON name, preserved
  `avoid` and extra keys, erased-row skipping, and unchanged `context_strings`
  rows/IDs/length and query joins.
- 2026-11-25: Confirmed there is no new `code_queries` migration and the new
  filename sorts after `20260605--unify-contexts-and-tutors.sql`; both are
  asserted in the test module.
- 2026-11-25: Ran `flask migrate --auto` against Phase 0 copies in
  `/tmp/opencode/learning_contexts_phase5/`.  CodeHelp (dev copy, not
  production-like): `context_strings` stayed at 9 rows / 1,490 characters,
  `code_queries` with a context stayed at 28, all 280 non-anonymized `{}` rows
  gained the full shape, and the one erased row stayed `{}`.  Starburst
  upgraded copy normalized its single `Default` context; the fresh Starburst
  copy had no context rows.  Neither Starburst copy has `context_strings` or
  `code_queries` tables.
- 2026-11-25: Fresh CodeHelp `flask initdb` created `context_strings` with the
  unchanged `id INTEGER PRIMARY KEY AUTOINCREMENT`, `ctx_str TEXT NOT NULL
  UNIQUE` shape, created no `learning_contexts` tables, and marked every
  migration (including the new one) applied.
- 2026-11-25: `pytest` 258 passed; `mypy` clean in 96 files; `ruff check` and
  `djlint src` clean.

### Phase 6 — App integration and documentation

**Status:** ☑ Done

- [x] **P6.1** Confirm the Starburst registration added in P1.4.
- [x] **P6.2** Verify Starburst behavior manually (no automated Starburst app
  fixture is added):
  - use a scratch Starburst database and start the app
  - confirm `context_strings` and `code_queries` do not exist in
    `sqlite_master`
  - create a context in the instructor config page and make it available
    "Now" (new contexts default to hidden)
  - confirm inquiry chats show context selection
  - confirm `context_help_form` is hidden without `code_queries`
  - confirm `context_inquiry_chat` remains available
  - confirm fresh-database `flask initdb` still creates no `context_strings`
    or `code_queries` table
- [x] **P6.3** Rewrite `src/codehelp/docs/contexts.md` for the two visible/
  hidden areas, with CS examples for details, general guidance, and terms and
  concepts to avoid.
- [x] **P6.4** Add `src/starburst/docs/contexts.md` with general examples.
- [x] **P6.5** Update related CodeHelp docs that mention contexts or the
  "avoid set" (for example `recommended_practices.md`).
- [x] **P6.6** Verify the component help text and docs link work when
  `contexts` is present in `docs_pages`.

**Notes:**

- 2026-11-25: Confirmed `src/starburst/__init__.py` registers
  `learning_contexts.gened_component` (P1.4).
- 2026-11-25: Manual Starburst check on a fresh scratch database:
  - No `context_strings` or `code_queries` tables exist after `init_db`, and
    there are no context rows.
  - The new-context form shows the Details, General guidance, and Terms and
    concepts to avoid fields.
  - Creating a context stored all four keys (`name`/`details`/`guidance`/`avoid`);
    updating it with empty fields stored all three content keys as empty
    strings.
  - After making the context available "Now", `/tutor/new` showed the Inquiry
    Chat form with the context chooser and the context name.
  - The config page showed the context docs link and the Inquiry Chat share
    link, but no Help form share link; the `/help/...` path returned 404, as
    expected without `code_queries`.
  - `/tutor/new/1?ctx_name=Default` returned 200 with the context preselected
    (`context_inquiry_chat`).
- 2026-11-25: Rewrote `src/codehelp/docs/contexts.md` around the visible
  **Details** area and the hidden **Additional instructions** area, with CS
  examples for Details, General guidance, and Terms and concepts to avoid.
  Removed the old separate "Environment and Tools" and "Keywords to Avoid"
  sections while keeping availability and configuration advice.
- 2026-11-25: Added `src/starburst/docs/contexts.md` with subject-neutral
  general examples (biology and literary analysis) for the same three fields.
- 2026-11-25: Updated `src/codehelp/docs/recommended_practices.md` to refer to
  the "Terms and concepts to avoid" area instead of the old avoid set.
- 2026-11-25: Aligned `src/starburst/docs/contexts.md` with the later edits to
  the CodeHelp page: the "use or mention" wording, the broader General
  guidance description without a duplicate example, and the `### Names Only`
  / `### Additional Context` example headings.
- 2026-11-25: Verified `/docs/contexts` returns 200 in both applications, and
  the CodeHelp config page shows the docs link plus the subject-neutral help
  text.  `pytest` 258 passed; `mypy`, `ruff check`, and `djlint src` clean.

### Phase 7 — Verification and cleanup

**Status:** ☑ Done

- [x] **P7.1** `pytest` — 258 passed.
- [x] **P7.2** `mypy` — success, no issues in 96 source files.
- [x] **P7.3** `ruff check --fix` — all checks passed.
- [x] **P7.4** `djlint src` — 45 files linted, 0 errors.
- [x] **P7.5** Manual smoke test (exercised with Flask test clients against
  fresh scratch databases; the equivalent manual UI steps are listed in the
  final report):
  - create, edit, copy, and delete a context; make at least one available
  - student context chooser and description (including empty and
    whitespace-only `details`)
  - a CodeHelp query records the rendered context
  - repeating the same query context reuses the same `context_strings` row
  - class deletion removes class-only context strings and retains shared ones
  - a Starburst inquiry chat uses the selected context
  - class deletion works in both CodeHelp and Starburst (Starburst has no
    `code_queries` table)
  - Starburst has no `context_strings` table; CodeHelp and Starburst fresh
    databases both behave as specified
- [x] **P7.6** Grep for targeted stale references: `$.tools`, `name="tools"`,
  `tools=`, and `code_contexts`.  Do not treat every occurrence of the word
  "tools" as a stale reference.  Include `dev/lti_deep_linking.md` in the grep
  and either update it or document why it is out of scope.
- [x] **P7.7** Update the progress summary and running log below.

**Notes:**

- 2026-11-25: Full check suite is clean: `pytest` 258 passed, `mypy` clean in
  96 files, `ruff check --fix` clean, `djlint src` 0 errors across 45 files.
- 2026-11-25: P7.5 was exercised with two scratch-database smoke scripts
  (CodeHelp: 44 assertions; Starburst: 30 assertions) using the real app
  factories, `init_db`, local login, the instructor config routes, the student
  chooser, `/help/request`, the inquiry-chat route, and the class-deletion
  route.  Both scripts passed.
  - CodeHelp confirmed: `context_strings` keeps its original shape and unique
    constraint; no `contexts` table is created by `learning_contexts`; every
    migration is marked applied; a new context starts hidden and stores
    `name`/`details`/`guidance`/`avoid`; editing and copying preserve the full
    JSON shape; the chooser shows `details` but never `guidance` or `avoid`;
    whitespace-only `details` yields an empty description; a query stores the
    full rendered context; repeating it reuses the same `context_strings` row;
    class deletion nulls the class queries' `context_string_id`, removes
    class-only strings, retains a string shared with another class, and
    anonymizes the context config to `{}` with a `[deleted]` name.
  - Starburst confirmed: no `context_strings`, `code_queries`, or `contexts`
    table after `init_db`; context create/edit/copy/delete and availability
    work; `/tutor/new` shows the context details but not guidance or avoid
    terms; an inquiry chat's stored system prompt contains all three fields;
    class deletion anonymizes the context config and still works without a
    `code_queries` table.
- 2026-11-25: P7.6 found no stale references in tracked source, templates,
  tests, or docs.  The only `code_contexts` references are in
  `dev/lti_deep_linking.md`, which is still untracked user work and predates
  this refactor (it describes the old component name and line numbers); it was
  deliberately left unchanged and is out of scope for this change.  Intentional
  `$.tools`/`tools` mentions remain in the migration (reading the legacy key)
  and in migrated docs/fixtures (`**Environment and tools:**` example text).
  The now-unused `tools` config key no longer appears in any template or model.
- 2026-11-25: R3 (null before delete) and R6 (Starburst coverage) are verified
  by the automated tests plus the smoke run above.  R2 (deployment must run the
  migration before serving) and R4 (future strict per-class deletion) remain
  standing risks, not implementation tasks.


### File touch map

| Area | Files |
|---|---|
| Component package | `src/components/learning_contexts/{__init__.py,model.py,config_table.py,data.py,templates/context_edit_form.html,templates/context_chooser.html}` — no `schema.sql` |
| Consumers | `src/components/code_queries/{helper.py,data.py,schema.sql}`, `src/components/tutors/chat.py`, `src/components/tutors/chat_helpers.py`, `src/components/tutors/templates/tutor_new_form.html` |
| App factories | `src/codehelp/__init__.py`, `src/starburst/__init__.py` |
| Migration | `src/components/learning_contexts/migrations/20261125--learning-contexts--refactor.sql` |
| Test data | `tests/test_data.sql` |
| Tests | `tests/test_contexts_model.py`, `tests/test_contexts.py`, `tests/test_context_strings.py`, `tests/test_class_config.py`, `tests/test_helper.py`, `tests/test_privacy.py`, `tests/test_tutors.py`, `tests/test_lti.py`, `tests/test_migrations.py` |
| Docs | `src/codehelp/docs/contexts.md`, `src/starburst/docs/contexts.md`, `src/codehelp/docs/recommended_practices.md` |

### Open decisions and risks

- [x] **D1** **Resolved:** keep `context_strings` as a global dedup table.
  Production data shows roughly 41,000 references to 251 strings totaling
  about 500,000 characters; inlining would store about 80 MB more.  Ownership
  moves to `code_queries`; `learning_contexts` has no schema.
- [x] **D2** **Resolved:** do not split strings per class.  A shared string is
  also the other class's data; deleting it would corrupt that class's history,
  and per-class duplication would not remove the text from the system.  Orphan
  cleanup removes strings once no query references them.  Document that a
  shared string survives until its last reference is gone.
- [x] **D3** **Resolved:** there is one migration, the `learning_contexts`
  config JSON transform.  There is no `context_strings` migration, no table
  rebuild, no composite mapping, and no ordering requirement between the
  `learning_contexts` and `code_queries` components.  The transform must still
  sort after `20260605--unify-contexts-and-tutors.sql` on upgrades.
- [x] **D4** **Resolved:** the migration skips only erased rows where
  `config = '{}'` and `name LIKE '[deleted]%'`.  Non-anonymized `{}` rows are
  legacy empty configs and are transformed to `name` plus all three content
  keys, preserving the documented exception.
- [x] **D5** **Resolved:** keep the transform simple: normalize line endings,
  trim surrounding whitespace, and join old `tools` lines with `; `.  Do not
  split/clean individual lines or preserve markdown indentation.  Minor
  whitespace artifacts in legacy data are acceptable.
- [x] **D6** **Resolved:** Starburst integration is verified manually; no
  automated Starburst fixture is added in this change.
- [x] **D7** **Resolved:** do not add a runtime guard for old `tools` content;
  deployment must run `flask migrate` before serving the new code.
- [x] **D8** **Resolved:** readers treat missing content keys as empty; writers
  always emit all three content keys for non-erased rows.  Sparse serialization
  is not used.
- [x] **R1** Risk: the config JSON transform is pure SQL but now uses only
  `replace`, `trim`, `CASE`, and JSON functions; no recursive CTE or line
  splitting.  Cover normal, empty, CRLF, missing-key, non-anonymized `{}`, and
  skipped-erased-row cases in migration tests.
- [ ] **R2** Risk: `from_row()` silently drops old `tools` content.  The
  migration must run before the new code serves requests.  There is no runtime
  guard; deployment sequencing is the only control.
- [x] **R3** Risk: orphan cleanup must null `context_string_id` before
  deleting strings.  The `QueriesDeletionHandler` owns both steps, so this is
  local and order-independent relative to the contexts handler.  Verified by
  `tests/test_context_strings.py` and the P7.5 smoke run.
- [ ] **R4** Risk: if strict per-class deletion ever becomes a requirement,
  this design must be revisited.  It would require per-class duplication and a
  data migration, and it would still not remove the text from another class's
  own copy.
- [x] **R5** Risk: the migration depends on `config_items` having been created
  and populated by `20260605--unify-contexts-and-tutors.sql` on old databases.
  The `20261125` filename satisfies this; do not move it earlier.
- [x] **R6** Risk: Starburst behavior has no automated regression coverage.
  The Phase 0 copy checks, the P6.2 manual checklist, and the P7.5 Starburst
  smoke run are complete.  This remains a manual-only coverage gap for future
  changes.

### Verification commands

```sh
pytest
mypy
ruff check --fix
djlint src
```

For existing databases, the migration must be applied interactively before
the new code serves requests:

```sh
flask migrate
# or, to apply without prompting:
flask migrate --auto
```

### Running log

| Date | Phase / task | Note |
|---|---|---|
| 2026-11-22 | Plan added | Initial implementation checklist created after the spec revision. |
| 2026-11-25 | Spec review | Clarified the canonical JSON shape, exact combined-`details` format, composite migration mapping, Starburst deletion without `code_queries`, handler transaction/foreign-key behavior, test fixtures, indexes, and terminology. |
| 2026-11-25 | Migration plan | Split the one-time migrations by component: `code_queries` owns the context-string split/repoint; `learning_contexts` owns the config JSON transform and final table/index creation.  The `code_queries` migration must sort first.  Added required migration regression tests.  *(Superseded by the fourth and fifth review entries.)* |
| 2026-11-25 | Fourth review | Production data (~41,000 references, 251 strings, ~500,000 chars) shows dedup saves ~80 MB, so the table stays.  Dropped the per-class split and the `code_queries` context-string migration; moved table ownership to `code_queries`; kept orphan cleanup in `QueriesDeletionHandler`; the only remaining migration is the config JSON transform. |
| 2026-11-25 | Fifth review | Clarified the migration ordering constraint (`20260605--unify-contexts-and-tutors.sql`), decided to skip anonymized `{}` rows, specified strict whitespace/blank-line cleanup, chose manual-only Starburst verification, and chose deployment-only migration sequencing.  Corrected the test-plan references and added migration/privacy risks. |
| 2026-11-25 | Sixth review | Documented the read/write shape: missing content keys read as empty, writers always emit all three; `{}` is the erased shape only.  Narrowed the migration skip to erased rows, required name population, `COALESCE`, tab-aware trimming, and a transaction; added non-anonymized `{}` and `test_tutors.py` corrections. |
| 2026-11-25 | Migration simplification | Replaced strict per-line cleanup and recursive splitting with line-ending normalization, outer trimming, and `; ` joining of old `tools`; reduced migration tests to normal/empty/missing-key/CRLF cases. |
| 2026-11-25 | Phase merge | Merged former Phase 4 (context strings and data layer) into Phase 1 so the rename, schema/function move, and deletion-handler changes land atomically; added the missing user-deletion cleanup test case. |
| 2026-11-25 | Phase 0 complete | Baseline clean (245 tests, mypy, ruff, djlint).  Recorded scratch database copies and pre-migration state.  No production-like CodeHelp copy was available, so the dev DB fallback was used and documented; the old Starburst DB was upgraded to the current pre-refactor state and a fresh Starburst DB was also created. |
| 2026-11-25 | Phase 1 complete | Moved `context_strings` DDL/function to `code_queries`, simplified context deletion, added query-orphan cleanup, renamed the package to `learning_contexts`, registered it in Starburst, and updated tests.  `pytest` 246 passed; mypy/ruff/djlint clean.  Manual Starburst table and class-deletion checks passed. |
| 2026-11-25 | Phase 2 complete | Replaced `tools` with `details`/`guidance`/`avoid`; rewrote prompt and student description; added legacy/missing-key model tests; migrated shared fixtures to the new JSON shape and updated prompt-label expectations.  `pytest` 253 passed; mypy/ruff/djlint clean. |
| 2026-11-25 | Phase 3 complete | Rewrote the context edit form with visible Details and a grouped hidden-instructions area, made component help text subject-neutral, and added form/edit-view/empty-description tests.  `pytest` 255 passed; mypy/ruff/djlint clean. |
| 2026-11-25 | Phase 5 complete | Added the `learning_contexts` config JSON transform migration and `tests/test_migrations.py`; exercised `flask migrate --auto` on the Phase 0 CodeHelp/Starburst copies and verified the fresh CodeHelp `initdb` path.  Context-string rows and query references were unchanged, erased rows stayed `{}`, and Starburst still has no `context_strings`/`code_queries` tables.  `pytest` 258 passed; mypy/ruff/djlint clean. |
| 2026-11-25 | Phase 6 complete | Confirmed Starburst registration and manual behavior on a fresh scratch database (no `context_strings`/`code_queries`, context create/edit and availability, inquiry-chat selection, hidden Help form link, working Inquiry Chat link).  Rewrote CodeHelp `contexts.md`, added Starburst `contexts.md`, and updated `recommended_practices.md`.  Docs and config-page links verified in both apps.  `pytest` 258 passed; mypy/ruff/djlint clean. |
| 2026-11-25 | Phase 7 complete | All checks clean (`pytest` 258 passed; mypy/ruff/djlint clean).  Exercised CodeHelp (44 assertions) and Starburst (30 assertions) end-to-end on fresh scratch databases: context create/edit/copy/delete/availability, student chooser and description, query context recording and dedup, inquiry-chat context use, class deletion and anonymization, and the no-`context_strings`/no-`code_queries` Starburst guarantees.  Stale-reference grep found only the untracked `dev/lti_deep_linking.md` (documented as out of scope) plus intentional legacy `tools` migration/fixture text. |
