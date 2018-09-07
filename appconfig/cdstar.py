import os

from pycdstar.api import Cdstar
from cdstarcat.resources import RollingBlob

SERVICE_URL = os.environ.get('CDSTAR_URL')
USER = os.environ.get('CDSTAR_USER')
PWD = os.environ.get('CDSTAR_PWD')


class NamedBitstream(object):
    def __init__(self, oid, bs):
        self.oid = oid
        self.bitstream = bs

    @property
    def url(self):
        return '{0}/bitstreams/{1}/{2}'.format(SERVICE_URL, self.oid, self.name)

    @property
    def name(self):
        return self.bitstream.id


def get_api():
    return Cdstar(service_url=SERVICE_URL, user=USER, password=PWD)


def add_backup_user(oid):
    obj = get_api().get_object(oid)
    obj.acl.update(read=['backup', 'clld'], write=['backup', 'clld'])


def get_latest_bitstream(oid):
    bs = RollingBlob(oid=oid).latest(get_api())
    if bs:
        return NamedBitstream(oid, bs)


def add_bitstream(oid, fname):
    rb = RollingBlob(oid=oid)
    api = get_api()
    # Add the sql dump as latest bitstream ...
    rb.add(api, str(fname))
    rb.expunge(api, keep=10)
