Developer Documentation
=======================

This document provides information for developers working on the Gen-Ed
framework and applications built on it.  It covers the project structure,
development environment setup, and contributing guidelines.  For instructions
on how to install and run the applications, see `README.md`.


## Project Structure

The project repository contains several key files and directories at its root level:

- **pyproject.toml:** Located at the project root, this is the central
  configuration file for the Python project, defining metadata, dependencies,
  and settings for tools like Ruff, mypy, djlint, and pytest.
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
    - **components/:** Self-contained, reusable components providing specific
      features (e.g., code queries, tutors). Each application is built by
      combining a set of these components.
    - **codehelp/, starburst/:** Application packages, each
      containing a Flask/Gen-Ed app factory that assembles and configures a set
      of components from `src/components/` to create a complete application.
    - **[dir]/templates:** Jinja2 templates. Templates in an
      application-specific or component-specific directory often extend base
      templates found in `src/gened/templates`.
    - **[dir]/migrations:** Database migration scripts. Scripts in
      `src/gened/migrations/` apply to the common schema. Component-specific
      migrations are located in subdirectories within
      `src/components/[component_name]/migrations/`, and application-specific
      migrations can be found in `src/[application_name]/migrations/`. All are
      applied using the custom migration command: `flask --app [application] migrate`.
- **tests/:** Contains unit and integration tests for the Gen-Ed framework and
  the CodeHelp applications.  Most tests are executed on instances of CodeHelp,
  even when testing functionality solely contained in `src/gened/`, and
  Starburst is not tested.
- **dev/:** Includes scripts and tools for development tasks, such as testing
  prompts and evaluating models.

### src/gened/

- **base.py:** Defines the `GenEdAppBuilder` class, which application factories
  in each app's `__init__.py` use to build and configure a Flask app with
  Gen-Ed components.
- **schema_common.sql:** The initial database schema for tables common to all
  Gen-Ed applications. Used when creating a new database with `flask initdb`.

Most other files in the framework provide utility functions and Flask routes
for functionality common to all Gen-Ed applications.  A few of the more
important ones:

- **admin/:** Administrator interfaces.
- **class_config/** Provides a generic mechanism for components to define and
  manage configuration items on a per-class basis.
- **auth.py:** User session management and authorization, including
  login/logout.  Generally, only the admin users are "local," with credentials
  stored in the database.  For most users, authentication is handled via either
  OpenID Connect (in `oauth.py`) or LTI (`lti.py`).
- **classes.py:** Routes for creating new classes and switching between classes
  (as a student).
- **db.py:** Database connections and operations, including CLI commands
  (see `flask --app [application] --help` for a list of commands).
- **llm.py:** Configuring, selecting, and using LLMs.

### src/[application]/

A few applications included in the repository.  Each application includes one
or more Gen-Ed components as its core functionality, wrapping them in the
general user- and class-management code provided by Gen-Ed.

- **__init__.py:** Defines the Flask application factory `create_app()`, which
  is the entry point to the application. It instantiates a `GenEdAppBuilder`
  and adds the required components (e.g., `code_queries`, `tutors`) from
  `src/components/` to build the full Flask app.  It also sets configuration
  values specific to the application.
- **schema.sql:** An optional file for the initial schema of any tables unique
  to the application. Most schema definitions are now located within their
  respective components (e.g., `src/components/code_queries/schema.sql`). It is
  used alongside `schema_common.sql` and component schemas when creating a new
  database with `flask initdb`.
- **templates/:** Jinja2 templates -- any that need to be customized
  specifically for CodeHelp.  Note that many of these are used by routes
  defined in `src/gened/` -- in those cases, the route's code is generic, but
  some aspect of the page contents are still application-specific.

### src/components/[component]/

Each component is defined in its own subpackage under `src/components/`. A
component encapsulates a specific piece of functionality (e.g., a query
interface, a tutor) that can be reused across different Gen-Ed applications.

A component is integrated into an application via a `GenEdComponent` object,
which should be defined in and exporetged from  the component's `__init__.py`
file. This object tells the `GenEdAppBuilder` how to wire the component into
the application.

A typical component directory includes:
- **`__init__.py`**: Defines and exports the `gened_component` object.
- **`helper.py`** or similar: Contains the component's core logic, including
  the Flask Blueprint for its routes.
- **`data.py`** or similar: Defines data sources, admin charts, and data
  deletion handlers for the component.
- **`prompts.py`** (if applicable): Contains prompts for use with LLMs.
- **`schema.sql`** (if applicable): The database schema for any tables the
  component requires.
- **`migrations/`** (if applicable): A directory for database migration
  scripts.
- **`templates/`**: A directory for the component's Jinja2 templates.

The `GenEdComponent` object is a dataclass that aggregates all the pieces of
the component that the Gen-Ed framework needs to know about. See
`src/gened/base.py` for the definition and use of its parameters.

To create a new component, a developer can create a new directory in
`src/components`, structure it as described above, and then add its
`gened_component` to the desired application in `src/[application]/__init__.py`
using `builder.add_component()`.


## Development

### Setting up the Development Environment; Running an Application

See the instructions in `README.md`.

### Running Tests

First, install test dependencies:

```sh
pip install -e .[test]
```

Run all tests:

```sh
pytest
```

For code coverage report (currently only codehelp and the components it
includes are tested):

```sh
pytest --cov=src/gened --cov=src/components --cov=src/codehelp --cov-report=html && xdg-open htmlcov/index.html
```

### Type Checking, Code Style, and Standards

The project uses mypy for static type checking (in strict mode), and Ruff and
djLint for linting and style checks.  These are all configured in
`pyproject.toml`.

We recommend installing the checkers using a tool like
[uv](https://docs.astral.sh/uv/concepts/tools/)
or
[pipx](https://pipx.pypa.io/)
.

Run the checks from the project root:
- Type checking: `mypy`
- Python linting: `ruff check`
- Template linting: `djlint -`

All new code should pass these checks. Code should be correctly typed with no
mypy errors (ignoring unavoidable errors from third-party libraries lacking
type information).

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
`src/gened/migrations/`, `src/[application_name]/migrations/`, and in any of
the application's component directories (`src/components/[component_name]/migrations/`).
Typically, typing `A` at the prompt to apply all new migrations will bring your
database schema up to date. Note that this command modifies an *existing* database; use
`flask initdb` only when creating a *new* database from scratch.

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

