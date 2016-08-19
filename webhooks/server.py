# -*- coding: utf-8 -*-
"""
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

GITHUB_IGNORE_LABEL = os.getenv('GITHUB_IGNORE_LABEL', 'pr_ignore')


class Rule(object):

    def __init__(self, desc, quantifier, fn):
        self.desc = desc
        self.quantifier = quantifier
        self.fn = fn

    def __repr__(self):
        return self.desc, self.quantifier, self.fn

    def validate(self, lines):
        if self.quantifier([self.fn(line) for line in lines]):
            # rule is satisfied
            return None
        # else, we return the description of the rule violated
        return self.desc


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

    def __init__(self, api_key, api_secret, owner, repo):
        self.api_key = api_key
        self.api_secret = api_secret
        self.owner = owner
        self.repo = repo

    def make(self, path, method='get', params=None, data=None):
        url = "{base}/repos/{owner}/{repo}/{path}".format(
            base=GITHUB_API_BASE,
            owner=GITHUB_OWNER,
            repo=GITHUB_REPO,
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


def _prefix_story_link_in_pull_request(id):
    g = Github(
                os.getenv('GITHUB_USERNAME'),
                os.getenv('GITHUB_TOKEN'),
                GITHUB_OWNER,
                GITHUB_REPO
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

    Returns:
        bool: True if description meets criterias, else False
        list[str]: list of criterias not met, else None
    """
    lines = description.split('\n')
    rules = PR_RULES.copy()
    for rule_name in ignore_list:
        rules.pop(rule_name)


    issues = [
        i for i in _yield_rule_adherence(rules.values(), lines)
        if i is not None
    ]
    return bool(not any(issues)), issues


def _validate_pull_request_description(id):
    """
    Validate Pull request's description, and makes comment on the Pull
    request on quality.

    Args:
        id (int): Pull request ID
    """

    g = Github(
                os.getenv('GITHUB_USERNAME'),
                os.getenv('GITHUB_TOKEN'),
                GITHUB_OWNER,
                GITHUB_REPO
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
            issues_printed = '\n- '.join([''] + issues)
            comment = txt.read().format(issues=issues_printed)
            g.comment_on_pull_request(id, comment)


def _handle_github_pull_request_event(payload):
    if payload.get('zen'):
        # status check
        print('ping pong')
        return None

    action = payload.get('action')
    id = payload.get('number')  # pull request ID

    if action:
        if action in ('opened', 'reopened'):
            _prefix_story_link_in_pull_request(id)

        if action == 'edited':
            _validate_pull_request_description(id)

        return None

    return ValueError('unable to process action from Github hook')


@app.route('/')
def index():
    return flask.render_template('index.html')


@app.route('/github/payload', methods=['POST'])
def github_payload():
    payload = flask.request.get_json(
        force=True,
        silent=True,
        cache=False)

    if not payload:
        flask.abort(400)

    err = _handle_github_pull_request_event(payload)
    if err:
        flask.abort(500)

    return 'ok'
