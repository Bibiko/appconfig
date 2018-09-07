from appconfig import cdstar


def test_NamedBitstream(mocker):
    mocker.patch.multiple(
        'appconfig.cdstar', SERVICE_URL='http://example.org/', USER='u', PWD='pwd')

    class Bitstream(object):
        id = 'y'

    nbs = cdstar.NamedBitstream('x', Bitstream())
    assert 'example.org' in nbs.url
    assert nbs.name == 'y'


def test_add_bitstream(mocker, testdir):
    class RB(mocker.Mock):
        add = mocker.Mock()
        _sorted_bitstreams = [mocker.Mock(), mocker.Mock()]

        def sorted_bitstreams(self, _):
            return self._sorted_bitstreams

    mocker.patch('appconfig.cdstar.RollingBlob', RB)
    cdstar.add_bitstream('oid', testdir / 'apps.ini')
    assert RB.add.called
