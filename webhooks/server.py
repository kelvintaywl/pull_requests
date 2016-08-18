# -*- coding: utf-8 -*-
"""
"""
import json
import os

import requests
import flask

app = flask.Flask(__name__)


app.config.update(dict(
    DEBUG=True
))

GITHUB_OWNER = 'kelvintaywl'
GITHUB_REPO = 'pull_requests'
GITHUB_API_BASE = 'https://api.github.com'


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


def _handle_github_event(payload):
    if payload.get('zen'):
        print('ping pong')
        return None

    action = payload.get('action')
    if action:
        if action in ('opened', 'reopened'):
            id = payload.get('number')
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
            body = "story: {}\r\n{}".format(
                link,
                pr['body'])

            g.update_pull_request(id, title=title, body=body)

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

    err = _handle_github_event(payload)
    if err:
        flask.abort(500)

    return 'ok'
