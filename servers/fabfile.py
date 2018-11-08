from fabric.api import run, task, sudo, settings, env
from fabric.tasks import execute
from fabric.contrib.console import confirm
from fabric.contrib.files import exists
from dateutil.parser import parse

from appconfig import APPS
from appconfig.config import App
from appconfig.tasks.deployment import pip_freeze

env.hosts = APPS.hostnames
ACC = []  # A global accumulator to store results across tasks


from appconfig.tasks import letsencrypt


@task
def ls():
    """list installed clld apps"""
    sudo('supervisorctl avail')
    sudo('psql -l', user='postgres')


@task
def renew_certs():
    if confirm("Renew certificates: " + env.host_string + "?", default=False):
        letsencrypt.require_certbot()
        if exists('/etc/letsencrypt/live'):
            certs = set(sudo('ls -1 /etc/letsencrypt/live').split())
        else:
            certs = set()
        apps = set(a.domain for a in APPS.values() if a.production == env['host'])
        apps.add(env['host'])
        for cert in certs - apps:
            # Obsolete certificate! The app is no longer deployed on this host.
            letsencrypt.delete(cert)
        for app in apps - certs:
            letsencrypt.require_cert(app)

        with settings(warn_only=True):
            letsencrypt.renew()


@task
def last_deploy():
    global ACC
    with settings(warn_only=True):
        for a in APPS.values():
            if a.production == env.host and exists(str(a.config)):
                res = parse(run('stat -c "%y" {0}'.format(a.config)))
                ACC.append((a.name, res))
    if env.host == env.hosts[-1]:
        maxname = max(len(t[0]) for t in ACC)
        for a, dt in sorted(ACC, key=lambda t: t[1], reverse=True):
            print('{0}{1}'.format(
                a.ljust(maxname + 1), dt.isoformat().replace('T', ' ').split('.')[0]))


@task
def pip_freeze_all():
    """
    Attempts to write requirements.txt files for all apps in apps.ini into
    their respective apps folder.
    """

    def helper(app):
        if type(app) is App:
            execute(pip_freeze, app, host=app.production)

    with settings(warn_only=True):
        for a in APPS.values():
            helper(a)
