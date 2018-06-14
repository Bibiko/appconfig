from urllib.request import HTTPError

import pytest


def test_ls(capsys):
    from appconfig.__main__ import ls

    ls([])
    out, err = capsys.readouterr()
    assert 'wals3' in out

    ls(['-p'])
    out, err = capsys.readouterr()
    assert 'wals3' in out


def test_error(mocker):
    from appconfig.__main__ import test_error

    mocker.patch('appconfig.__main__.urlopen')

    with pytest.raises(RuntimeError):
        test_error('wals3')

    mocker.patch(
        'appconfig.__main__.urlopen', mocker.Mock(side_effect=HTTPError('', 500, '', {}, None)))
    test_error('wals3')
