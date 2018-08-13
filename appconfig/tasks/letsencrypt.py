from fabric.api import sudo
from fabtools import require


def require_certbot():
    require.deb.ppa('ppa:certbot/certbot')
    require.deb.packages(['software-properties-common', 'python-certbot-nginx'])


def require_cert(app):
    require_certbot()
    sudo('certbot --nginx -n -d {0} certonly'.format(app.domain))


def renew():
    require_certbot()
    sudo('certbot --nginx -n renew')
