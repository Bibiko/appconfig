from fabric.api import sudo
from fabtools import require


def require_certbot():
    require.deb.ppa('ppa:certbot/certbot')
    require.deb.packages(['software-properties-common', 'python-certbot-nginx'])


def require_cert(domain):
    # If an App instance is passed, we lookup its domain attribute:
    sudo('certbot --nginx -n -d {0} certonly'.format(getattr(domain, 'domain', domain)))


def delete(cert):
    sudo('certbot delete --cert-name {0}'.format(cert))


def renew():
    sudo('certbot --nginx -n renew')
