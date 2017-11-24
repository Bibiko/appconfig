# __main__.py - command line interface

from __future__ import unicode_literals, print_function

import argparse

from ._compat import urlopen, HTTPError

from . import APPS


def ls():
    apps = sorted(APPS.values(), key=lambda a: (a.production, a.name))
    table = [(a.name, a.domain, a.production, a.stack) for a in apps]
    cwidth = tuple(max(map(len, c)) for c in zip(*table))
    tmpl = '{:%d} {:%d} {:%d} {:%d}' % cwidth
    print(tmpl.format('id', 'domain', 'server', 'stack'))
    print(tmpl.format(*('-' * w for w in cwidth)))
    for r in table:
        print(tmpl.format(*r))


def test_error(appid):
    """Test the error reporting of an app by requesting its /_raise URL."""
    raise_url = 'http://{0.domain}/_raise'.format(APPS[appid])
    try:
        u = urlopen(raise_url)
    except HTTPError as e:
        assert e.code == 500
    else:
        u.close()
        raise RunimeError('url %r did not raise' % url)


def main():  # pragma: no cover
    parser = argparse.ArgumentParser(prog='appconfig', description='')
    parser.add_argument('command', choices=['ls', 'test_error'])
    parser.add_argument('args', nargs=argparse.REMAINDER)
    args = parser.parse_args()

    if args.command == 'ls':
        ls()
    elif args.command == 'test_error':
        test_error(args.args[0])
    else:
        raise NotImplementedError
