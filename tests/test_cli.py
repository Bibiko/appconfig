from urllib.error import HTTPError

import pytest

from appconfig.__main__ import main


def test_ls(capsys):
    main(['ls'])
    out, err = capsys.readouterr()
    assert 'wals3' in out

    main(['ls', '-p'])
    out, err = capsys.readouterr()
    assert 'wals3' in out


def test_error(mocker):
    mocker.patch('appconfig.commands.test_error.urlopen')

    with pytest.raises(RuntimeError):
        main(['test_error', 'wals3'])

    mocker.patch(
        'appconfig.commands.test_error.urlopen',
        mocker.Mock(side_effect=HTTPError('', 500, '', {}, None)))
    main(['test_error', 'wals3'])
