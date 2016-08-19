# Pull Requests

We deserve better pull requests as collaborators in any software project.


## Introduction

This is more of a concept or prototype to explore how we can give better
structures to pull requests in Github without making documentation on pull
requests more painful (but fun and rewarding perhaps).

## Usage

### Templates

It's always good to set a default pull request template for your repository.

For me and my current workflow, there's a standard template i try to follow.

You can view the [template here](.github/PULL_REQUEST_TEMPLATE.md)

### Validating Pull Request descriptions

You can set up a server to validate pull request descriptions based on certain
rules.

In this repo, i have created a Flask application that listens to pull request
events from GitHub.

See the [code here](webhooks/server.py) for more information.

To use this sample server, simply fork it or so, and deploy it via Heroku.

#### steps to deploy on Heroku

1. go to your Heroku account and create a new application
2. link your forked repository.
3. set `GITHUB_USERNAME` and `GITHUB_TOKEN` enviornment variables in Heroku dashboard with your GitHub handler and access token.
4. optionally, you can set a `GITHUB_IGNORE_LABEL` environment variable. When a pull request has a label of that value, this server ignores validation

## Todo

- use OAuth client instead of specific GitHub user
- include PR rule coverage
- customizing of rule weightage for coverage
- add more rules (optional)
