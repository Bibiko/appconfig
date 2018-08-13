from fabric.api import task, sudo

from appconfig.tasks import letsencrypt


@task
def ls():
    """list installed clld apps"""
    sudo('supervisorctl avail')
    sudo('psql -l', user='postgres')


@task
def renew_certs():
    letsencrypt.renew()
