Developer Documentation
=======================

This document provides an overview of the source code for the Gen-Ed project
and its included applications, outlining its structure and key components to
facilitate development and contributions.


## Project Structure

The project repository contains several key files and directories at its root level:

- **pyproject.toml:** Located at the project root, this is the central
  configuration file for the Python project, defining metadata, dependencies,
  and settings for tools like Ruff and mypy.
- **instance/:** Also located at the project root (typically), this directory is
  configured via the `FLASK_INSTANCE_PATH` environment variable (usually set
  in `.env`). It holds persistent runtime-generated files not tracked by Git,
  primarily the application's SQLite database (`[...].db`), but also backups
  and/or files for domain verification (`.well-known/`).
- **src/:** Contains the primary source code for both the Gen-Ed framework and
  the applications built on it.
    - **gened/:** The code for the Gen-Ed framework itself, containing all
      code *shared* by all Gen-Ed applications. This includes functionality
      such as authentication, database management, and LTI integration.
    - **codehelp/:** Code specific to the CodeHelp application, primarily
      focused on interfaces and functionality for specific queries made in
      CodeHelp.  This covers both student users, instructors, and admin interfaces.
    - **starburst/:** Code specific to the Starburst application.
    - **[dir]/templates:** Jinja2 templates, with templates in an
      application-specific directory often extending base templates in
     `src/gened/templates`.
    - **[dir]/migrations:** Database migration scripts. Scripts in
      `src/gened/migrations/` apply to the common schema, while scripts in an
      application-specific directory (e.g., `src/codehelp/migrations/`) apply
      only to that application's schema. These are applied using the custom
      migration command: `flask --app [application] migrate`.
- **dev/:** Includes scripts and tools for development tasks, such as testing
  prompts and evaluating models.
- **tests/:** Contains unit and integration tests for the Gen-Ed framework and
  the CodeHelp applications.  Most tests are executed on instances of CodeHelp,
  even when testing functionality solely contained in `src/gened/`, and
  Starburst is not tested.

### src/gened/

- **base.py:** `create_app_base()` is an application factory that instantiates
  a base Flask app for an application like CodeHelp or Starburst to further
  build on and customize.
- **schema_common.sql:** The initial database schema for tables common to all
  Gen-Ed applications. Used when creating a new database with `flask initdb`.

Most other files in the framework provide utility functions and Flask routes
for functionality common to all Gen-Ed applications.  A few of the more
important ones:

- **admin.py:** Administrator interfaces.
- **auth.py:** User session management and authorization, including
  login/logout.  Generally, only the admin users are "local," with credentials
  stored in the database.  For most users, authentication is handled via either
  OpenID Connect (in `oauth.py`) or LTI (`lti.py`).
- **class_config.py:** Provides a generic mechanism for configuring classes, to
  be customized by each individual application based on what a "class" needs to
  store in that application.
- **classes.py:** Routes for creating new classes and switching between classes
  (as a student).
- **db.py:** Database connections and operations, including CLI commands
  (see `flask --app [application] --help` for a list of commands).
- **llm.py:** Configuring, selecting, and using LLMs.

### src/codehelp/

CodeHelp is the more complex and more actively developed application in the repository.

- **__init__.py:** Defines a Flask application factory `create_app()`, called
  by Flask when run as `flask --app codehelp run`.  This is the entry point to
  the entire application.
- **schema.sql:** The initial schema for application-specific tables (e.g.,
  those unique to CodeHelp). Used alongside `schema_common.sql` when creating
  a new database with `flask initdb`.
- **helper.py:** The main help interface for students using CodeHelp.  Routes
  and functions for inputting queries and viewing responses.
- **prompts.py:** Defines the LLM prompts used by the main help interface.
- **tutor.py:** An unreleased, in-development alternative interface with a
  back-and-forth chat modality.
- **templates/:** Jinja2 templates -- any that need to be customized
  specifically for CodeHelp.  Note that many of these are used by routes
  defined in `src/gened/` -- in those cases, the route's code is generic, but
  some aspect of the page contents are still application-specific.

### src/starburst/

Starburst is a simpler application than CodeHelp, and it serves as a good
example on which to base a new Gen-Ed application.  It is structured in the
same way as CodeHelp, minus just a few files.


## Development

### Setting up the Development Environment; Running an Application; Testing

See the instructions in `README.md`.

### Running Tests

Ensure test dependencies are installed (`pip install -e .[test]`). Run the test
suite using `pytest` from the project root. Check code coverage with
`pytest --cov=src/...` (see `README.md` for the full command). Use `mypy` for
static type checking (see "Code Style and Standards" below).

### Updates

#### Dependencies

If dependencies in `pyproject.toml` change, your environment may no longer have
the correct libraries installed.  To be sure you have all dependencies
installed, run:

```sh
pip install -U -e .[test]
```

#### Database Schema

If the database schema changes (e.g., due to pulling new code), your development
database (typically stored in `instance/`) will be outdated, and the application
may crash. To update an existing database to the latest schema, use the custom
migration tool provided by Gen-Ed (via the `gened.migrate` module):

```sh
flask --app [application_name] migrate
```

This command finds and applies any pending migration scripts located in
`src/gened/migrations/` and `src/[application_name]/migrations/`. Typically,
typing `A` at the prompt to apply all new migrations will bring your database
schema up to date. Note that this command modifies an *existing* database; use
`flask initdb` only when creating a *new* database from scratch.

### Code Style and Standards

The project uses Ruff and djLint for linting and style checks (configured in
`pyproject.toml`) and mypy for static type checking (in strict mode).

The `mypy` package is installed as part of the project's optional test
dependencies using the command from `README.md`:
```sh
pip install -e .[test]
```

We recommend installing the other checkers using a tool like
[pipx](https://pipx.pypa.io/).

Run the checks from the project root:
- Python linting: `ruff check`
- Template linting: `djlint -`
- Type checking: `mypy`

All new code should pass these checks. Code should be correctly typed with no
mypy errors (ignoring unavoidable errors from third-party libraries lacking
type information).

### Contributing

Contributions to the project are welcome!  Please follow these steps:

1. Fork the repository.
2. Create a new branch for your feature or bug fix.
3. Make your changes and commit them to the branch with descriptive messages.
4. Run `mypy` to check for type errors in the new code.  Correct any you find.
5. Run `pytest` to run tests.  Ensure they all pass.
6. Push your changes to your fork.
7. If the main repository has changed since you made your branch, please
   merge the new main into your branch *or* rebase onto the latest commit.
8. Submit a pull request to the main repository.
9. In the pull request, you will be asked to sign the CLA found in
   `contributors/contributor_license_agreement.md`.

