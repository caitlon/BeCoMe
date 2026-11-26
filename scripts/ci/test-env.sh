# Source this file, do not run it:  . scripts/ci/test-env.sh
#
# Puts a shell in the environment every test run starts from: it exports each line of
# tests/test.env and removes the LangSmith variables the library reads from the process.
# tests/conftest.py applies the same list inside pytest and the CI jobs append it to
# $GITHUB_ENV, so a script that starts the tests or the API here gets the same safe
# setup. A variable in the process beats .env, which on a developer machine can name a
# live mail provider, a tracing key or a model host.
#
# Source it before anything the script sets itself, so a more specific value (an
# E2E database URL, a secret key) is set afterwards and wins.

set -a
# shellcheck source=tests/test.env
. "$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")/../.." && pwd)/tests/test.env"
set +a

unset LANGSMITH_API_KEY LANGSMITH_ENDPOINT LANGSMITH_PROJECT
unset LANGCHAIN_API_KEY LANGCHAIN_ENDPOINT LANGCHAIN_PROJECT
