"""Used for testing against multiple version of Python."""

import nox


@nox.session(python=['3.8', '3.9', '3.10', '3.11'])
def test_and_typing(session):
    session.install('.[test,dev]')
    session.run('pytest', 'tests')
    session.run('mypy', 'rt')


@nox.session()
def lint(session):
    session.install(".[test,dev]")
    session.run('ruff', 'rt')
