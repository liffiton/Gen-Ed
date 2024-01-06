Gen-Ed: Generative AI for Education
===================================

Gen-Ed is a framework for building web applications that use generative AI
(LLMs) for education (i.e., organized around instructors and their classes of
students for use in teaching and learning contexts).

This repository also contains two applications that are built on Gen-Ed:

1. **CodeHelp** [1,2]: A tool for assisting students in computer science
   classes without giving them solution code. <https://codehelp.app/>

2. **Starburst**: A topic-exploration tool for writing assignments.
   <https://strbrst.xyz/>

#### References

[1] [CodeHelp: Using Large Language Models with Guardrails for Scalable Support
in Programming Classes](https://arxiv.org/abs/2308.06921). Mark Liffiton, Brad
Sheese, Jaromir Savelka, and Paul Denny. 2023. In Proceedings of the 23rd Koli
Calling International Conference on Computing Education Research (Koli Calling
'23).

[2] [Patterns of Student Help-Seeking When Using a Large Language Model-Powered
Programming Assistant](https://arxiv.org/abs/2310.16984). Brad Sheese, Mark
Liffiton, Jaromir Savelka, and Paul Denny. 2024. In Proceedings of the 26th
Australasian Computing Education Conference (ACE '24).  DOI:
[10.1145/3636243.3636249](https://doi.org/10.1145/3636243.3636249)


Install
-------

Requires Python 3.9 or higher.

1. Create and activate a Python virtual environment.

2. Install the Gen-Ed package and bundled applications in 'editable' mode:

```sh
pip install -e .
```


Set Up an Application
---------------------

1. In the root of the repository, create an instance folder for the database:

```sh
mkdir instance
```

2. In the root of the repository, create `.env` and populate it:

```
FLASK_INSTANCE_PATH=instance
SECRET_KEY=[a secure random string -- used to sign session cookies]
OPENAI_API_KEY=[your OpenAI API key]
```

Optionally, set any of the following pairs with IDs/secrets obtained from
registering your application with the given authentication provider:

```
GOOGLE_CLIENT_ID=[...]
GOOGLE_CLIENT_SECRET=[...]
GITHUB_CLIENT_ID=[...]
GITHUB_CLIENT_SECRET=[...]
MICROSOFT_CLIENT_ID=[...]
MICROSOFT_CLIENT_SECRET=[...]
```

Then, to set up the CodeHelp app, for example:

3. Initialize database:

```sh
flask --app codehelp initdb
```

4. Create at least one admin user:

```sh
flask --app codehelp newuser --admin [username]
```

This will create and display a randomly-generated password.
To change the password:

```sh
flask --app codehelp setpassword [username]
```


Running an Application
----------------------

For example, to run the CodeHelp app:

```sh
flask --app codehelp run

# or, during development:
flask --app codehelp --debug run
```


Running Tests
-------------

First, install test dependencies:

```sh
pip install -e .[test]
```

Run all tests:

```sh
pytest
```

For code coverage report:

```sh
pytest --cov=src/gened --cov=src/codehelp --cov-report=html && xdg-open htmlcov/index.html
```

For mypy type checking:

```sh
mypy
```


Author
------

Gen-Ed and the included applications are by Mark Liffiton.


Licenses
--------

Gen-Ed and the included applications are licensed under the GNU Affero General
Public License version 3 (AGPL-3.0-only).

Brand icons from [Simple Icons](https://simpleicons.org/) are licensed under
CC0-1.0.  Other icons from [Lucide](https://lucide.dev/) are licensed under the
Lucide ISC license.

For the text of these licenses, see the LICENSES directory.
