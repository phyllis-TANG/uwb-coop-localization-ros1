# Independent catkin workspace setup

Complete [`repository_sync.md`](repository_sync.md) first. The commands below
assume that the GitHub repository has been published, cloned at the stated path,
and contains the latest committed workspace skeleton.

The repository owns the `ros_ws` workspace. Its generated `build`, `devel`,
`install`, and `logs` directories are ignored by Git. Do not create this
workspace inside a Wheeltec workspace and do not run `catkin_make` in any
Wheeltec directory.

## Initialize and build

Open a fresh terminal in the vendor VM. Change to the root of the cloned
repository, replacing the example path if the clone is elsewhere:

```bash
cd "$HOME/uwb-coop-localization-ros1" && \
test -d .git && test -f README.md && test -d ros_ws/src && \
catkin_init_workspace ros_ws/src && \
catkin_make -C ros_ws
```

The `test` checks stop the command if the current repository structure is not
present. `catkin_init_workspace` creates catkin's top-level CMake link inside
`ros_ws/src`; `catkin_make -C ros_ws` then builds only this repository's
workspace. Generated files are excluded by `.gitignore`.

## Verify isolation

After the build succeeds, run:

```bash
printf '%s\n' '--- workspace ---'; readlink -f ros_ws; \
printf '%s\n' '--- generated directories ---'; \
find ros_ws -maxdepth 1 -type d -printf '%f\n' | sort; \
printf '%s\n' '--- repository changes ---'; git status --short
```

Success means:

- the resolved workspace path is inside this repository;
- `build`, `devel`, and `src` are listed;
- no Wheeltec path was created or modified;
- `git status --short` has no generated build output.

### Recorded build verification

The operator reported the following verification result on 2026-09-16:

```text
--- workspace ---
/home/wheeltec-client/uwb-coop-localization-ros1/ros_ws
--- generated directories ---
build
devel
ros_ws
src
--- repository changes ---
?? ros_ws/.catkin_workspace
```

The workspace path and generated directories are correct. The only reported
change was catkin's generated workspace-root marker. It is not source code and
is now excluded by the repository `.gitignore`; it must not be committed.

Do not source `ros_ws/devel/setup.bash` or edit `.bashrc` yet. First retain the
complete output from both commands so the clean workspace build can be verified.
