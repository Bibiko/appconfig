# __main__.py - command line interface

from __future__ import unicode_literals, print_function

import argparse

from . import APPS


def ls():
    apps = sorted(APPS.values(), key=lambda a: (a.production, a.name))
    table = [(a.name, a.domain, a.production) for a in apps]
    cwidth = tuple(max(map(len, c)) for c in zip(*table))
    tmpl = '{:%d} {:%d} {:%d}' % cwidth
    print(tmpl.format('id', 'domain', 'server'))
    print(tmpl.format(*('-' * w for w in cwidth)))
    for r in table:
        print(tmpl.format(*r))


def main():  # pragma: no cover
    parser = argparse.ArgumentParser(prog='appconfig', description='')
    parser.add_argument('command', choices=['ls'])
    args = parser.parse_args()
    if args.command == 'ls':
        ls()
    else:
        raise NotImplementedError
