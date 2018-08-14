from fabric.api import sudo
from fabtools import require

from appconfig import APPS


def require_certbot():
    require.deb.package('software-properties-common')
    require.deb.ppa('ppa:certbot/certbot')
    require.deb.package('python-certbot-nginx')


def require_cert(domain):
    # If an App instance is passed, we lookup its domain attribute:
    sudo('certbot --nginx -n -d {0} certonly --agree-tos --email {1}'.format(
        getattr(domain, 'domain', domain), APPS.defaults['error_email']))


def delete(cert):
    sudo('certbot delete --cert-name {0}'.format(cert))


def renew():
    sudo('certbot --nginx -n renew')
