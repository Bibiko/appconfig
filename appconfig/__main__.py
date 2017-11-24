from __future__ import unicode_literals, print_function
import sys

from clldutils.clilib import ArgumentParser
from clldutils.markup import Table

from appconfig import APPS


def ls(args):
    t = Table('id', 'domain', 'server')
    for app in sorted(APPS.values(), key=lambda app: (app.production, app.name)):
        t.append((app.name, app.domain, app.production))
    print(t.render(tablefmt='simple'))


def main():  # pragma: no cover
    parser = ArgumentParser('appconfig', ls)
    sys.exit(parser.main())
