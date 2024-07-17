Developer Documentation
=======================

This document provides an overview of the source code for the Gen-Ed project
and its included applications, outlining its structure and key components to
facilitate development and contributions.


## Project Structure

The project is organized into several directories:

- **src:** Contains the primary source code for both the Gen-Ed framework and
  the applications built on it.
    - **gened:** The code for the Gen-Ed framework itself, this contains all
      code *shared* by all Gen-Ed applications.  This includes functionality
      such as authentication, database management, and LTI integration.
    - **codehelp:** Code specific to the CodeHelp application, primarily
      focused on interfaces and functionality for specific queries made in
      CodeHelp.  This covers both student users, instructors, and admin interfaces.
    - **starburst:** Code specific to the Starburst application.
    - **[dir]/templates:** Jinja2 templates, with templates in an
      application-specific directory often extending base templates in
     `src/gened/templates`.
    - **[dir]/migrations:** Migration scripts, either for all Gen-Ed
      applications (in `src/gened/migrations/`) or application-specific.  Run
      `flask --app [application] migrate` for a simple migration interface to
      apply them.
- **dev:** Includes scripts and tools for development tasks, such as testing
  prompts and evaluating models.
- **tests:** Contains unit and integration tests for the Gen-Ed framework and
  the CodeHelp applications.  Most tests are executed on instances of CodeHelp,
  even when testing functionality solely contained in `src/gened/`, and
  Starburst is not tested.

### src/gened/

- **base.py:** `create_app_base()` is an application factory that instantiates
  a base Flask app for an application like CodeHelp or Starburst to further
  build on and customize.
- **schema_common.sql:** The database schema for all tables used in any Gen-Ed
  application.

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
- **openai.py:** Configuring, selecting, and using OpenAI LLMs.

### src/codehelp/

CodeHelp is the more complex and more actively developed application in the repository.

- **__init__.py:** Defines a Flask application factory `create_app()`, called
  by Flask when run as `flask --app codehelp run`.  This is the entry point to
  the entire application.
- **schema.sql:** The schema for any application-specific tables (that are not
  common to all Gen-Ed applications and thus cannot be in
  `src/gened/schema_shared.sql`).
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

### Updates

#### Dependencies

If dependencies in `pyproject.toml` change, your environment may no longer have
the correct libraries installed.  To be sure you have all dependencies
installed, run:

```sh
pip install -U -e .[test]
```

#### Database Schema

If any database schema changes, your development database (typically stored in
`instance/`) will be outdated, and the application may crash.  To update a
database to the latest schema, use the migration tool built in to Gen-Ed:

```sh
flask --app [application_name] migrate
```

Typically, typing `A` to apply all new migrations will get your database into
working order.

### Code Style and Standards

The project is configured to use Ruff for linting and style checks (with
exceptions defined in `pyproject.toml`) and mypy for type checking (in strict
mode).  Run `ruff check` in any folder to check for issues, and run `mypy` in
the project root to check types.  All code should be correctly typed with no
type errors outside of issues caused by 3rd-party libraries without typing
information.

### Contributing

Contributions to the project are welcome!  Please follow these steps:

1. Fork the repository.
2. Create a new branch for your feature or bug fix.
3. Make your changes and commit them to the branch with descriptive messages.
4. Run `mypy` to check for type errors in the new code.  Correct any you find.
5. Push your changes to your fork.
6. If the main repository has changed since you made your branch, please
   merge the new main into your branch *or* rebase onto the latest commit.
7. Submit a pull request to the main repository.
8. In the pull request, you will be asked to sign the CLA found in
   `contributors/contributor_license_agreement.md`.

