# dapla-composer-build-scripts

Reusable GitHub Actions workflows and composite actions used to build, push and
deploy the container images that back Dapla Composer sources.

Each supported language has its own **self-contained** reusable workflow named
`<language>-image.yaml`. They all follow the same pattern: read a language
manifest from the caller's repository, resolve the runtime version and a
[Cloud Native Buildpacks](https://buildpacks.io/) builder, then build and push
the image to the team's Artifact Registry (GAR).

## Image build workflows

| Workflow                                                     | Language | Manifest         |
|--------------------------------------------------------------|----------|------------------|
| [`python-image.yaml`](.github/workflows/python-image.yaml)   | Python   | `pyproject.toml` |

> Additional languages are added by dropping in another `<language>-image.yaml`
> workflow that follows the same structure (see
> [Adding a new language image](#adding-a-new-language-image)).

### Common structure

Every image workflow is triggered via
[`workflow_call`](https://docs.github.com/en/actions/using-workflows/reusing-workflows)
and shares the same two jobs and environment.

#### Inputs

The image workflows take **no inputs**. The source directory is hardcoded via the
workflow-level `PYPROJECT_DIR` env variable (Python: `automation/composer/python`),
and the published image name is fixed per workflow (Python:
`automation/composer/python`).

#### Environment

The following values are configured as workflow-level `env` and drive where the
source is read from, where the image is published, and how authentication happens:

| Variable           | Value                                                                                            |
|--------------------|--------------------------------------------------------------------------------------------------|
| `AR_PROJECT_ID`    | `artifact-registry-5n`                                                                            |
| `AR_LOCATION`      | `europe-north1`                                                                                   |
| `GCP_WIF_PROVIDER` | Workload Identity Federation provider used to authenticate to Google Cloud (keyless, OIDC-based). |
| `PYPROJECT_DIR`    | Path to the directory containing the language manifest/source (`automation/composer/python`). |

#### Job: `resolve`

Reads configuration from the caller's repository and exposes it as job outputs
for the build step:

- **Team** – reads `metadata.team_name` from `metadata/team-info.yaml` and derives
  the Artifact Registry repository (`<team>-docker`) and the deploy service
  account (`gh-actions-<team>@<project>.iam.gserviceaccount.com`). This part is
  identical for every language.
- **Runtime version** – parses the language manifest to determine the runtime
  version (Python: `project.requires-python` from `pyproject.toml`).
- **Builder** – maps the runtime version to a Cloud Native Buildpacks builder
  image (Python: `3.11`–`3.13` → `gcr.io/buildpacks/builder:google-22`,
  `3.14` → `gcr.io/buildpacks/builder:latest`).
- **Dependencies** – emits the manifest's dependency list as compact single-line
  JSON so it can be safely written to `$GITHUB_OUTPUT`.

#### Job: `build_and_push`

- Authenticates to Google Cloud using Workload Identity Federation and the
  resolved team service account.
- Configures Docker for the team's Artifact Registry.
- Uses `pack` (Cloud Native Buildpacks) to build the image from the source
  directory with the resolved builder and runtime version.
- Pushes the image with three tags:
  - `:latest`
  - `:<version>` (e.g. `:3.11`)
  - `:<version>-<git-sha>`

### Expected caller layout

A repository that calls an image workflow is expected to provide:

```text
metadata/team-info.yaml   # contains metadata.team_name (used by every language)
<src_dir>/<manifest>      # language manifest, e.g. pyproject.toml for Python
```

### Example usage

```yaml
jobs:
  build-image:
    uses: statisticsnorway/dapla-composer-build-scripts/.github/workflows/python-image.yaml@python-image-v1.0.0
    permissions:
      contents: read
      id-token: write
```

> The source directory is hardcoded in the workflow via `PYPROJECT_DIR`. If your
> manifest is not at the repository root, set `PYPROJECT_DIR` accordingly in the
> workflow.

## Adding a new language image

To add support for a new language (for example R), create a new self-contained
workflow the same way `python-image.yaml` is built:

1. Copy `.github/workflows/python-image.yaml` to
   `.github/workflows/r-image.yaml`.
2. Rename the source env variable (e.g. `PYPROJECT_DIR` → `DESCRIPTION_DIR`) and
   point it at the R manifest (`DESCRIPTION` / `renv.lock`).
3. In the `resolve` job, keep the **Team** block unchanged and replace only the
   language-specific parts: how the runtime version is parsed and how it maps to
   a Buildpacks `builder`.
4. In `build_and_push`, adjust the manifest path and any language-specific
   `--env` values passed to `pack`.

Because each workflow is self-contained, adding a language never changes the
existing ones. The team resolution, GCP auth and push steps are simply copied and
kept in sync across the `<language>-image.yaml` files.

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
[`version.yaml`](version.yaml). Callers should pin to a released tag (for
example `@python-image-v1.0.0`) rather than a moving branch.

## License

Distributed under the terms of the [MIT license][license],
_dapla-composer-build-scripts_ is free and open source software.

<!-- github-only -->

[license]: https://github.com/statisticsnorway/ssb-project-cli/blob/main/LICENSE
