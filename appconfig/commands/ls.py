"""
List registered apps.
"""
from clldutils.clilib import Table, add_format


def register(parser):
    parser.add_argument('-p', '--port', default=False, action='store_true', help='Sort by port')
    add_format(parser, default='simple')


def run(args):
    table = []
    for a in args.apps.values():
        table.append((
            a.name,
            'https://{0}'.format(a.domain),
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

    if args.port:
        sortkey = lambda t: t[3]
    else:
        sortkey = lambda t: (t[2], t[0])

    with Table(args, '#', 'id', 'url', 'server', 'port', 'stack', 'public') as t:
        for i, r in enumerate(sorted(table, key=sortkey)):
            t.append(['{0}'.format(i + 1)] + list(r))
