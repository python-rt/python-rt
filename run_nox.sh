#!/bin/bash

echo "Run this script with -R in order to not re-install dependencies on every run."
echo ""
echo ""

export PYENV_ROOT="$HOME/.pyenv"
[[ -d $PYENV_ROOT/bin ]] && export PATH="$PYENV_ROOT/bin:$PATH"
eval "$(pyenv init -)"

nox "$@"
