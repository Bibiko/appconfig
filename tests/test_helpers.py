from appconfig import helpers

def test_getpwd(mocker):
    mocker.patch('appconfig.helpers.getpass', mocker.Mock(getpass=mocker.Mock(return_value='abc')))
    assert helpers.getpwd('x') == 'abc'
