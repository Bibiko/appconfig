"""
Test the error reporting of an app by requesting its /_raise URL.
"""
from urllib.request import urlopen
from urllib.error import HTTPError


def register(parser):
    parser.add_argument('app', help='APP ID')


def run(args):
    raise_url = 'https://{0.domain}/_raise'.format(args.apps[args.app])
    try:
        u = urlopen(raise_url)
    except HTTPError as e:
        assert e.code == 500
    else:
        u.close()
        raise RuntimeError('url %r did not raise' % raise_url)
