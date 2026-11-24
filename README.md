# dapla-composer-build-scripts

Reusable GitHub Actions workflows and composite actions used to:

- Build and push container images for Dapla Composer sources.
- Validate and test Airflow DAGs.

## Statomaten workflow

[`statomaten.yaml`](.github/workflows/statomaten.yaml) is the single reusable
entry point for DAG checks and Composer Python image builds. It is triggered via
[`workflow_call`](https://docs.github.com/en/actions/using-workflows/reusing-workflows)
and takes no inputs.

The `statomaten_inputs` job runs
[`tools/statomaten_inputs.py`](tools/statomaten_inputs.py), which compares the
event's base and head commits and decides what to run:

- **DAG checks** run on pull requests for each changed
  `automation/statomaten/<project>/dags` directory.
- **Image builds** run for each `automation/statomaten/<project>/pyproject.toml`
  that changed, on any event that invokes the workflow. Changes to other files
  (including lock files) do not trigger a build.

The caller controls which events invoke the workflow. Since a changed
`pyproject.toml` on a pull request also publishes an image, only invoke the
workflow for trusted code with access to the required Google Cloud identity.

### Example usage

```yaml
on:
  pull_request:
  push:
    branches: [main]

jobs:
  statomaten:
    uses: statisticsnorway/dapla-composer-build-scripts/.github/workflows/statomaten.yaml@<release-tag>
    permissions:
      contents: read
      id-token: write
```

### Expected caller layout

```text
metadata/team-info.yaml                    # contains metadata.team_name (always required)
automation/statomaten/<project>/
  pyproject.toml                           # must set project.requires-python
  dags/                                    # Airflow DAGs and their tests
```

Each `<project>` folder is built as its own image. A `pyproject.toml` at the
repository root is ignored.

### Image configuration

For each changed project, the Python version is the highest supported version
satisfying `project.requires-python`, and selects the Buildpacks builder:

| Python | Builder |
|--------|---------|
| `3.11`–`3.13` | `gcr.io/buildpacks/builder:google-22` |
| `3.14` | `gcr.io/buildpacks/builder:latest` |

If no supported version satisfies `requires-python`, the workflow fails.

The `build_and_push` job authenticates with Workload Identity Federation using
service account `gh-actions-<team>@artifact-registry-5n.iam.gserviceaccount.com`,
builds from `automation/statomaten/<project>` using
[Cloud Native Buildpacks](https://buildpacks.io/), and pushes to
`europe-north1-docker.pkg.dev/artifact-registry-5n/<team>-docker/automation/composer/<project>`
with the tags `latest`, `<project>-<python_version>` and
`<project>-<python_version>-<git-sha>`.

## DAG checks

The `check-dags` job in [`statomaten.yaml`](.github/workflows/statomaten.yaml)
validates changed Airflow DAGs and runs their `pytest` tests on pull requests.

It checks each project under `automation/statomaten/*/dags` and uses the dependencies and validator in [`check-dags/`](check-dags/).

## Composite action: `wait-for-status`

[`.github/actions/wait-for-status`](.github/actions/wait-for-status/action.yaml)
polls the combined status checks on a pull request's head commit and waits for
the requested statuses to succeed, failing fast if any of them fail or if the
timeout is reached. It is useful for gating on external status reporters (for
example Atlantis plans).

| Input             | Default | Description                                                       |
|-------------------|---------|-------------------------------------------------------------------|
| `statuses`        | —       | Newline-delimited list of status contexts to wait for (required). |
| `timeout`         | `300`   | Seconds to poll before timing out.                                |
| `sleep_time`      | `5`     | Seconds to wait between polls.                                     |
| `initial_sleep`   | `10`    | Seconds to wait before the first poll.                            |
| `fail_on_destroy` | `true`  | Reserved for failing when a plan wants to destroy resources.      |

## Versioning

The currently published version is tracked in
[`version.yaml`](version.yaml). Callers should pin to a released tag containing
`statomaten.yaml` rather than a moving branch.

## License

Distributed under the terms of the [MIT license][license],
_dapla-composer-build-scripts_ is free and open source software.

<!-- github-only -->

[license]: https://github.com/statisticsnorway/ssb-project-cli/blob/main/LICENSE
