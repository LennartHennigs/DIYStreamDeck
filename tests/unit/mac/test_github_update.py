"""Tests for src/mac/github_update.py — latest code.py fetch (mocked network)."""
from unittest import mock

import pytest

from src.mac import github_update


def test_repo_url():
    assert github_update.REPO_URL == 'https://github.com/LennartHennigs/DIYStreamDeck'


def test_latest_ref_uses_release_tag():
    with mock.patch('src.mac.github_update._fetch', return_value='{"tag_name": "v2.0.0"}'):
        assert github_update.latest_ref() == 'v2.0.0'


def test_latest_ref_falls_back_to_branch_when_no_release():
    with mock.patch('src.mac.github_update._fetch',
                    side_effect=github_update.UpdateError('HTTP 404')):
        assert github_update.latest_ref() == github_update.DEFAULT_BRANCH


def test_latest_code_py_fetches_raw_at_ref():
    calls = {}

    def fake_fetch(url):
        calls['last'] = url
        if url == github_update._API_LATEST:
            return '{"tag_name": "v1.2.3"}'
        return '# code.py contents'

    with mock.patch('src.mac.github_update._fetch', side_effect=fake_fetch):
        ref, text = github_update.latest_code_py()

    assert ref == 'v1.2.3'
    assert text == '# code.py contents'
    assert calls['last'].endswith('/v1.2.3/src/pi_pico/code.py')


def test_latest_code_py_propagates_offline_error():
    def fake_fetch(url):
        if url == github_update._API_LATEST:
            raise github_update.UpdateError('offline')
        raise github_update.UpdateError('Could not reach GitHub (offline?)')

    with mock.patch('src.mac.github_update._fetch', side_effect=fake_fetch):
        with pytest.raises(github_update.UpdateError, match='offline'):
            github_update.latest_code_py()
