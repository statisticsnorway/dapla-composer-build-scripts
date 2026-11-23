# /// script
# requires-python = ">=3.14"
# dependencies = ["packaging", "pyyaml"]
# ///

import json
import os
import subprocess
import sys
import tomllib
from pathlib import Path

import yaml
from packaging.specifiers import SpecifierSet
from packaging.version import Version


def main():
    try:
        write_outputs()
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        print(error, file=sys.stderr)
        raise SystemExit(1) from error


def write_outputs():
    output_file = os.environ["GITHUB_OUTPUT"]
    with Path(output_file).open("a", encoding="utf-8") as file:
        file.writelines(f"{name}={value}\n" for name, value in outputs().items())


def outputs():
    _changed_dag_folders = changed_dag_folders()
    return {
        "should_build_image": str(git_diff("pyproject.toml")).lower(),
        "should_test_dags": str(bool(_changed_dag_folders)).lower(),
        "folders_with_changed_dags": " ".join(_changed_dag_folders),
        "python_version": python_version(),
        "builder": builder(),
        "dependencies": packages(),
        "ar_repository": f"{team_name()}-docker",
        "service_account": service_account(),
    }


def team_name():
    with Path("metadata/team-info.yaml").open(encoding="utf-8") as file:
        return yaml.safe_load(file)["metadata"]["team_name"]


def service_account():
    return f"gh-actions-{team_name()}@{os.environ['AR_PROJECT_ID']}.iam.gserviceaccount.com"


def pyproject():
    with Path("pyproject.toml").open("rb") as file:
        return tomllib.load(file)


def packages():
    return json.dumps(
        pyproject()["project"].get("dependencies", []), separators=(",", ":")
    )


def python_version():
    requirement = SpecifierSet(pyproject()["project"]["requires-python"])
    supported_versions = builders()
    for version in supported_versions:
        if Version(version) in requirement:
            return version  # return the highest compatible python version
    raise ValueError(
        f"No supported Python version satisfies requires-python={requirement!s}"
    )


def builder():
    version = python_version()
    try:
        return builders()[version]
    except KeyError as error:
        raise ValueError(f"Python {version} is not supported") from error


def builders():
    return {
        "3.14": "gcr.io/buildpacks/builder:latest",
        "3.13": "gcr.io/buildpacks/builder:google-22",
        "3.12": "gcr.io/buildpacks/builder:google-22",
        "3.11": "gcr.io/buildpacks/builder:google-22",
    }


def changed_dag_folders():
    return [
        str(path)
        for path in sorted(Path("automation/statomaten").glob("*/dags"))
        if path.is_dir() and git_diff(str(path))
    ]


def git_diff(path):
    result = subprocess.run(
        ["git", "diff", "--quiet", base_sha(), head_sha(), "--", path],
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
