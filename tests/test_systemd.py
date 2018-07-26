from appconfig import systemd


def test_enable(app, testdir, mocker):
    files = mocker.Mock(upload_template=mocker.Mock())
    mocker.patch('appconfig.systemd.files', files)
    mocker.patch('appconfig.systemd.sudo')
    systemd.enable(app, testdir / 'systemd')
    assert files.upload_template.call_count == 3
