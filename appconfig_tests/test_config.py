# test_config.py

import pytest

from appconfig import config


def test_app():
    app = config.App(**{k: '1' for k in config.App._fields})

    assert app.name == app.test == app.production == '1'
    assert app.port == app.workers == app.deploy_duration == 1
    assert app.with_blog == app.pg_collkey == app.pg_unaccent == True
    assert app.require_deb == app.require_pip == ['1']
    assert app.home / 'spam' == app.config / 'spam' == app.www / 'spam'

    with pytest.raises(ValueError, match='missing'):
        config.App(**{k: '1' for k in config.App._fields if k != 'name'})

    with pytest.raises(ValueError, match='unknown'):
        config.App(nonfield='', **{k: '1' for k in config.App._fields})


def test_app_fixture(app):
    assert app.name and app.test and app.production 


def test_app_replace(app):
    assert app.replace().__dict__ == app.__dict__
    assert app.replace(require_deb='spam eggs').require_deb == ['spam', 'eggs']
    assert app.replace(require_deb='').require_deb is not app.require_deb

    with pytest.raises(ValueError, match='unknown'):
        app.replace(nonfield='')
