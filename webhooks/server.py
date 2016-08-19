# -*- coding: utf-8 -*-
"""
    Pull Request Bot

    This server listens to webhooks from Github such that
    when you create / update a pull request, it checks the description,
    such that:


    When opening a new pull request:

    1. if branch name has a story ticket to Pivotal where its name follow:
    '[ticket ID]-test-branch', it prefixes a link to the description:
        ```story: https://pivotaltracker.com/story/show/[ticket ID]```


    When editing a pull request:


    1. if description of pull request meets current rules, it posts a LGTM
    comment (update `webhooks/static/good_comment.txt` for content).
    Else, we post a comment signalling the issues
    (see `webhooks/static/issues.txt`).

    If you prefer to ignore all rules for the pull request,
    you can simply add a `pr_ignore` label to the pull request.
    That value can be modified if you set an environment variable
    `GITHUB_IGNORE_LABEL` with the specific label name.


    NOTE:

    Please set `GITHUB_USERNAME` and `GITHUB_TOKEN` environment variables
    in the server. It would use these values to authenticate for GitHub API
    requests.

"""
import json
import os

import requests
import flask

app = flask.Flask(__name__)

CURRENT_DIR = os.path.dirname(os.path.realpath(__file__))
STATIC_DIR = os.path.join(CURRENT_DIR, 'static')


app.config.update(dict(
    DEBUG=True
))

GITHUB_OWNER = 'kelvintaywl'
GITHUB_REPO = 'pull_requests'
GITHUB_API_BASE = 'https://api.github.com'

# label name to detect if we should ignore rules when validating
# pull request description; else we would apply all rules @ PR_RULES
GITHUB_IGNORE_LABEL = os.getenv('GITHUB_IGNORE_LABEL', 'pr_ignore')


class Rule(object):
    """
    Rule class that defines what makes a good pull request description.

    It applies validation on description with its `validate` method.

    Note:

        self.fn should be a function that returns True if the provided
        text meets the rule criteria.

    Example:

        # we create a Rule instance to check that all lines start with 'The'
        >>> empty_line_rule = Rule(
        >>>    "all lines start with 'The'", all, lambda x: x.startswith('The')
        >>>>)

    Args:
        desc (str): Human readable string describing the rule (imperative)
        quantifier (:obj:`function`): should be `any` or `all`
        fn (:obj:`function`): function to validate if text meets rule

    Attributes:
        desc (str): Human readable string describing the rule (imperative)
        quantifier (:obj:`function`): should be `any` or `all`
        fn (:obj:`function`): function to validate if text meets rule

    """
    def __init__(self, desc, quantifier, fn):
        self.desc = desc
        self.quantifier = quantifier  # should be `any` or `all`
        self.fn = fn  # rule function

    def validate(self, lines):
        """
        Validate that either one of the lines or all of the lines meet the
        rule.

        Whether it is just one of all of the lines,
        it depends on the value of self.quantifier

        Returns:
            str: description of rule if violated, else None
        """
        if self.quantifier([self.fn(line) for line in lines]):
            # rule is satisfied
            return None
        # else, we return the description of the rule violated
        return self.desc

# current list of all applicable rules
PR_RULES = {
    'story': Rule(
        "should have story link",
        any,
        lambda x: bool('story: ' in x)
    ),
    'todo': Rule(
        "all todos should be done",
        all,
        lambda x: bool('- [ ]' not in x)
    )
}


class Github(object):
    """
    Github API client class to make API calls on a specific repository
    of a certain owner.

    Only certain endpoints are implemented / supported.
    """

    def __init__(self, api_key, api_secret, owner, repo):
        self.api_key = api_key
        self.api_secret = api_secret
        self.owner = owner
        self.repo = repo

    def make(self, path, method='get',
             owner=GITHUB_OWNER, repo=GITHUB_REPO,
             params=None, data=None):
        """
        make API call to Github API.

        Args:
            path (str): API sub path
            method (str): lowercase HTTP method (e.g., `get`, `post`)
            owner (str): name of user/organization on GitHub
            repo (str): name of repository on GitHub
            params (dict): for GET parameters (querystring)
            data (dict): data paylod for POST requests
        """

        url = "{base}/repos/{owner}/{repo}/{path}".format(
            base=GITHUB_API_BASE,
            owner=owner,
            repo=repo,
            path=path)
        return requests.request(method, url,
                                params=params, data=data,
                                auth=(self.api_key, self.api_secret)
                                ).json()

    def get_pull_request(self, id):
        return self.make(
            'pulls/{id}'.format(
                id=id
            ),
            method='get'
        )

    def update_pull_request(self, id, title, body, state='open'):
        data = {
            'title': title,
            'body': body,
            'state': state
        }
        return self.make(
            'pulls/{id}'.format(
                id=id
            ),
            method='patch',
            data=json.dumps(data)
        )

    def comment_on_pull_request(self, id, comment):
        data = {
            'body': comment
        }
        return self.make(
            'issues/{id}/comments'.format(
                id=id
            ),
            method='post',
            data=json.dumps(data)
        )

    def get_issue(self, id):
        return self.make(
            'issues/{id}'.format(
                id=id
            ),
            method='get'
        )


def _prefix_story_link_in_pull_request(owner, repo, id):
    """

    """
    g = Github(
        os.getenv('GITHUB_USERNAME'),
        os.getenv('GITHUB_TOKEN'),
        owner,
        repo
    )
    pr = g.get_pull_request(id)

    title = pr['title']
    link = 'https://pivotaltracker.com/story/show/{id}'.format(
        id=pr['head']['ref'].split('-')[0]
    )
    body = "story: {}\r\n\n{}".format(
        link,
        pr['body'])
    g.update_pull_request(id, title=title, body=body)


def _yield_rule_adherence(rules, lines):
    for rule in rules:
        yield rule.validate(lines)


def _qualify_description(description, ignore_list=[]):
    """
    Check if description provided is good, based on criterias.

    Args:
        description (str): Pull request description
        ignore_list (list[str]): list of rule names to ignore. See PR_RULES

    Returns:
        bool: True if description meets criterias, else False
        list[str]: list of criterias not met, else None
    """
    lines = description.split('\n')

    # leave out specific rules if specified
    rules = PR_RULES.copy()
    for rule_name in ignore_list:
        rules.pop(rule_name)

    # grab all issues (which rules were violated)
    issues = [
        i for i in _yield_rule_adherence(rules.values(), lines)
        if i is not None
    ]
    return bool(not any(issues)), issues


def _validate_pull_request_description(owner, repo, id):
    """
    Validate Pull request's description, and makes comment on the pull
    request on quality. It sends a comment thereafter on the pull request
    to describe the quality of the pull request description

    Args:
        id (int): Pull request ID
    """

    g = Github(
        os.getenv('GITHUB_USERNAME'),
        os.getenv('GITHUB_TOKEN'),
        owner,
        repo
    )
    pr = g.get_pull_request(id)

    body = pr['body']

    issue = g.get_issue(id)
    ignore_list = []
    if 'pr_ignore' in (l['name'] for l in issue['labels']):
        ignore_list = PR_RULES.keys()

    ok, issues = _qualify_description(body, ignore_list=ignore_list)
    if ok:
        with open(
                os.path.join(STATIC_DIR, 'good_comment.txt')
        ) as txt:
            comment = txt.read()

            g.comment_on_pull_request(id, comment)
    else:
        with open(
            os.path.join(STATIC_DIR, 'issues.txt')
        ) as txt:
            # format issues into list items
            issues_printed = '\n- '.join([''] + issues)
            comment = txt.read().format(issues=issues_printed)

            g.comment_on_pull_request(id, comment)


def _handle_github_pull_request_event(payload):
    owner, repo = GITHUB_OWNER, GITHUB_REPO
    if payload.get('repo'):
        repo_name = payload['repo']['full_name']
        owner, repo = repo_name.split('/', 1)[:2]

    if payload.get('zen'):
        # status check
        print('ping pong')
        return None

    action = payload.get('action')
    id = payload.get('number')  # pull request ID

    if action:
        if action in ('opened', 'reopened'):
            _prefix_story_link_in_pull_request(owner, repo, id)

        if action == 'edited':
            _validate_pull_request_description(owner, repo, id)

        return None

    return ValueError('unable to process action from Github hook')


@app.route('/')
def index():
    """
    home page

    TODO: make it shiny
    """
    return flask.render_template('index.html')


@app.route('/github/payload', methods=['POST'])
def github_payload():
    """
    Callback endpoint for GitHub webhooks (POST)

    Currently, only supports for pull request events. Please see:
    https://developer.github.com/v3/activity/events/types/#pullrequestevent
    """
    payload = flask.request.get_json(
        force=True,
        silent=True,
        cache=False)

    if not payload:
        flask.abort(400)

    err = _handle_github_pull_request_event(payload)
    if err:
        flask.abort(500)

    return 'beep boop'
