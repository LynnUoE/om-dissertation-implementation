#!/usr/bin/env bash
# Deploy one commit of main; run by the CI/CD workflow over SSH (see docs/deploy-ec2.md).
#
# The workflow's SSH key is limited to this script in ~/.ssh/authorized_keys:
#   command="/home/ubuntu/litfinder/deploy/ci-deploy.sh",restrict ssh-ed25519 AAAA... github-actions
# so a leaked key can do nothing but deploy a commit that is already on origin/main.
# sshd passes what the client asked to run in SSH_ORIGINAL_COMMAND; the workflow sends the commit SHA.
set -euo pipefail

# In a function so bash has read the whole script before `git merge` replaces the file
main() {
    cd "$(dirname "$0")/.."
    local sha="${1:-${SSH_ORIGINAL_COMMAND:-}}"
    if [[ ! "$sha" =~ ^[0-9a-f]{40}$ ]]; then
        echo "Usage: ci-deploy.sh <full commit SHA>" >&2
        exit 2
    fi

    # Two pushes in a row: the second deployment waits for the first
    exec 9>"${TMPDIR:-/tmp}/litfinder-deploy.lock"
    flock 9

    git fetch --quiet origin main
    if ! git merge-base --is-ancestor "$sha" origin/main; then
        echo "$sha is not on origin/main; refusing to deploy it" >&2
        exit 1
    fi
    if git merge-base --is-ancestor "$sha" HEAD; then
        echo "$sha is already deployed (HEAD is $(git rev-parse --short HEAD))"
    else
        git merge --ff-only "$sha"
    fi
    deploy/deploy.sh
    echo "Deployed $(git rev-parse --short HEAD)"
}

main "$@"
exit
