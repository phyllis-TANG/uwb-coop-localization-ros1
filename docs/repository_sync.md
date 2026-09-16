# Repository checkout and synchronization

Do not run `git pull` blindly. First determine whether the repository is already
present, whether it has uncommitted work, and which GitHub remote and branch it
tracks. Pulling the wrong branch or overwriting local changes would make the
experiment environment harder to reproduce.

## Step 1: inspect without changing anything

Run this one command in the vendor VM:

```bash
repo="$HOME/uwb-coop-localization-ros1"; \
if git -C "$repo" rev-parse --is-inside-work-tree >/dev/null 2>&1; then \
  printf '%s\n' '--- repository found ---' "$repo" '--- remotes ---'; \
  git -C "$repo" remote -v; \
  printf '%s\n' '--- branch ---'; git -C "$repo" rev-parse --abbrev-ref HEAD; \
  printf '%s\n' '--- commit ---'; git -C "$repo" log -1 --oneline; \
  printf '%s\n' '--- status ---'; git -C "$repo" status --short --branch; \
else \
  printf '%s\n' 'REPOSITORY_NOT_FOUND' "$repo"; \
fi
```

This command is read-only. It reports either `REPOSITORY_NOT_FOUND` or the
existing clone's remote URL, branch, latest commit, and status.

`rev-parse --abbrev-ref HEAD` is used instead of `git branch --show-current`
because the Git version in the Ubuntu 18.04 vendor VM does not support the newer
`--show-current` option.

Send the complete output before continuing. The next command depends on the
result:

- If the repository is absent, obtain its actual GitHub HTTPS or SSH URL and
  clone it. A placeholder such as `<GITHUB_REPOSITORY_URL>` is not executable.
- If it exists with a clean working tree, fetch the recorded remote and compare
  local and remote commits before using a fast-forward-only pull.
- If it contains local changes, preserve and review them before any pull.
- If no remote is configured, add the actual GitHub URL only after verifying
  repository ownership and the intended branch.

The project owner identified the GitHub repository as
`https://github.com/phyllis-TANG/uwb-coop-localization-ros1.git`. This supersedes
the earlier lack of remote information; no new GitHub repository is needed.

## Recorded vendor-VM result

The operator ran the inspection on 2026-09-16 and received:

```text
REPOSITORY_NOT_FOUND
/home/wheeltec-client/uwb-coop-localization-ros1
```

This is expected for a VM that has not cloned the project. It is not a ROS or
catkin error.

## Step 2: clone the identified repository

Run this command in the vendor VM:

```bash
git clone https://github.com/phyllis-TANG/uwb-coop-localization-ros1.git \
  "$HOME/uwb-coop-localization-ros1" && \
git -C "$HOME/uwb-coop-localization-ros1" remote -v && \
git -C "$HOME/uwb-coop-localization-ros1" status --short --branch && \
git -C "$HOME/uwb-coop-localization-ros1" log -1 --oneline
```

`git clone` creates the missing project directory and checks out the remote's
default branch. The remaining commands print the configured remote, branch,
working-tree status, and current commit so the checkout can be verified before
catkin is run.

If Git reports that the repository is private or authentication failed, stop
and report the exact error. Do not put a password or token in the clone URL and
do not make the repository public merely to bypass authentication.

### Recorded clone result

The vendor VM successfully cloned the repository on 2026-09-16:

```text
origin  https://github.com/phyllis-TANG/uwb-coop-localization-ros1.git (fetch)
origin  https://github.com/phyllis-TANG/uwb-coop-localization-ros1.git (push)
## main...origin/main
e770d1e (HEAD -> main, origin/main, origin/HEAD) Merge pull request #1 from phyllis-TANG/codex/establish-ros1-software-skeleton
```

This verifies a clean `main` checkout tracking `origin/main`. Continue with the
workspace initialization in [`workspace_setup.md`](workspace_setup.md).
