# __main__.py - command line interface

from __future__ import unicode_literals, print_function

import argparse

from ._compat import urlopen, HTTPError

from . import APPS


def ls(args):
    """
    List registered apps.

    -p to sort by port
    """
    table = []
    for a in APPS.values():
        table.append((
            a.name,
            'http://{0}'.format(a.domain),
            a.production,
            '{0}'.format(a.port),
            a.stack,
            '{0}'.format(a.public)))
        if a.test:
            table.append((
                '{0} [test]'.format(a.name),
                'http://{0}/{1}'.format(a.test, a.name),
                a.test,
                '{0}'.format(a.port),
                a.stack,
                '{0}'.format(False)))
    cwidth = [2] + [max(map(len, c)) for c in zip(*table)]
    tmpl = ' '.join('{:%d}' % w for w in cwidth)
    print(tmpl.format('#', 'id', 'url', 'server', 'port', 'stack', 'public'))
    print(tmpl.format(*('-' * w for w in cwidth)))

    if args and '-p' in args:
        sortkey = lambda t: t[3]
    else:
        sortkey = lambda t: (t[2], t[0])

    for i, r in enumerate(sorted(table, key=sortkey)):
        r = ['{0}'.format(i + 1)] + list(r)
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
        raise RuntimeError('url %r did not raise' % raise_url)


def main():  # pragma: no cover
    parser = argparse.ArgumentParser(prog='appconfig', description='')
    parser.add_argument('command', choices=['ls', 'test_error'])
    parser.add_argument('args', nargs=argparse.REMAINDER)
    args = parser.parse_args()

    if args.command == 'ls':
        ls(args.args)
    elif args.command == 'test_error':
        test_error(args.args[0])
    else:
        raise NotImplementedError
