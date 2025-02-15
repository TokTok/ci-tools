#!/usr/bin/env bash

set -eux -o pipefail

git remote add upstream "$GITHUB_SERVER_URL/$GITHUB_REPOSITORY"
git remote -v
