# /// script
# requires-python = ">=3.14"
# dependencies = ["packaging", "pyyaml"]
# ///

import json
import logging
import os
import subprocess
import tomllib
from pathlib import Path

from packaging.specifiers import SpecifierSet
from packaging.version import Version


logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def main():
    try:
        write_outputs()
    except (OSError, ValueError, KeyError, subprocess.SubprocessError):
        logger.exception("Failed to resolve Statomaten inputs")
        raise SystemExit(1)


def write_outputs():
    resolved_outputs = outputs()
    for name, value in resolved_outputs.items():
        logger.info("%s=%s", name, value)
    output_file = os.environ["GITHUB_OUTPUT"]
    with Path(output_file).open("a", encoding="utf-8") as file:
        file.writelines(f"{name}={value}\n" for name, value in resolved_outputs.items())


def outputs():
    _dag_configurations = dag_configurations()
    return {
        "has_changed_dags": str(bool(_dag_configurations)).lower(),
        "dag_directories": " ".join(
            configuration["dag_folder_path"] for configuration in _dag_configurations
        ),
        "dag_upload_configurations": json.dumps(_dag_configurations, separators=(",", ":")),
        "image_configurations": json.dumps(
            image_configurations(), separators=(",", ":")
        ),
    }


def dag_configurations():
    return [
        {
            "project_id": project_id(path.parent.name),
            "project_name": path.parent.name,
            "dag_folder_path": str(path),
        }
        for path in sorted(Path("automation/statomaten").glob("*/dags"))
        if path.is_dir() and git_diff(str(path))
    ]


def project_id(project_name):
    team_name, environment = project_name.rsplit("-", 1)
    environment_code = environment[0]
    google_project_name = f"{team_name}-{environment_code}"
    result = subprocess.run(
        [
            "gcloud",
            "projects",
            "list",
            f"--filter=name:{google_project_name}",
            "--format=value(projectId)",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    project_ids = result.stdout.splitlines()
    if len(project_ids) != 1:
        raise ValueError(
            f"Expected one project with display name {project_name}, found {project_ids}"
        )
    return project_ids[0]


def image_configurations():
    return [
        {
            "path": str(path.parent),
            "name": path.parent.name,
            "python_version": str(python_version(path)),
            "builder": builder(path),
        }
        for path in sorted(Path("automation/statomaten").glob("*/pyproject.toml"))
        if git_diff(str(path.parent), f":(exclude){path.parent / 'dags'}")
    ]


def pyproject(path):
    with path.open("rb") as file:
        return tomllib.load(file)


def python_version(path):
    requirement = SpecifierSet(pyproject(path)["project"]["requires-python"])
    supported_versions = builders().keys()
    compatible_versions = (
        version for version in supported_versions if version in requirement
    )  # intersection of requirement range and supported versions
    try:
        return max(compatible_versions)
    except ValueError as error:
        raise ValueError(
            f"No supported Python version satisfies requires-python={requirement!s}"
        ) from error


def builder(path):
    version = python_version(path)
    try:
        return builders()[version]
    except KeyError as error:
        raise ValueError(f"Python {version} is not supported") from error


def builders():
    return {
        Version("3.14"): "gcr.io/buildpacks/builder:latest",
        Version("3.13"): "gcr.io/buildpacks/builder:google-22",
        Version("3.12"): "gcr.io/buildpacks/builder:google-22",
        Version("3.11"): "gcr.io/buildpacks/builder:google-22",
    }


def git_diff(*paths):
    result = subprocess.run(
        ["git", "diff", "--quiet", base_sha(), head_sha(), "--", *paths],
        check=False,
    )
    return result.returncode != 0


def base_sha():
    event = os.environ.get("GITHUB_EVENT_NAME")
    if event == "push":
        return os.environ.get("GITHUB_EVENT_BEFORE", "HEAD^")
    if event == "pull_request":
        event_path = os.environ.get("GITHUB_EVENT_PATH")
        if event_path:
            payload = json.loads(Path(event_path).read_text(encoding="utf-8"))
            return payload["pull_request"]["base"]["sha"]
    return "HEAD^"


def head_sha():
    return os.environ.get("GITHUB_SHA", "HEAD")


if __name__ == "__main__":
    main()
