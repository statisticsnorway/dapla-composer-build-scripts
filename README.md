# dapla-source-data-processor-build-scripts

## dapla-composer-build-scripts


This repository contains scripts used to build, deploy and test images used by `python_yaml`. The
process is controlled by the composite action `kildomaten.yaml`.

Every team IAC repo has an action that uses this composite action.
This is added
by `terraform-ssb-dapla-teams` [github-initializer](https://github.com/statisticsnorway/terraform-ssb-dapla-teams/tree/main/github/init#github-initializer).
The action is triggered when a `Kildomaten` source is added.

### Events

The action will perform different tasks based on the event that triggers it.

#### PR (pull_request event)

When a PR event involving changes to `automation/composer/python` occurs, the action will perform a set of tests on the
user-supplied code and configuration. If the tests finish successfully, it will post a comment on the PR stating that
the tests have passed and that the PR is ready for approval.

#### PR approved (pull_request_review event)

When a PR is approved, the tests are run again. If they succeed, an `atlantis apply` comment is posted by the action,
deploying the infrastructure needed for `python_yaml`.

#### Push to main (push event)

On push to the main branch, tests are executed, followed by building and pushing of the image to the team's GAR.
Then each Cloud Run instance will have a new revision created using the newly pushed image.

#### Manually triggered (workflow_dispatch event)

## License

Distributed under the terms of the [MIT license][license],
_dapla-composer-build-scripts_ is free and open source software.

<!-- github-only -->

[license]: https://github.com/statisticsnorway/ssb-project-cli/blob/main/LICENSE
