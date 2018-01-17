from fabric.api import task, sudo
from fabric.contrib import files
from fabtools import require, service

from appconfig import APPS
from appconfig.tasks.deployment import sudo_upload_template

APACHE_CFG = '/etc/munin/apache24.conf'
MUNIN_CFG = '/etc/munin/munin.conf'


def make_host_tree(hostnames):
    return '\n'.join('[%s]\n    address ssh://%s -W localhost:4949' % (h, h)
                     for h in hostnames)


def make_app_watchlist(apps):
    return ('[http-monitor]\n    env.urls ' +
            ' '.join('http://%s/_ping' % a.domain for a in apps))


@task
def munin_host():
    host_tree = make_host_tree(APPS.hostnames)
    app_watchlist = make_app_watchlist(APPS.values())

    require.deb.packages(['munin', 'apache2'])

    # Update WWW path:
    files.sed(MUNIN_CFG, '#htmldir /var/cache/munin/www',
              'htmldir /var/www/munin', use_sudo=True)

    # Update notification settings:
    files.sed(MUNIN_CFG,
              '#contact.someuser.command mail -s "Munin notification" somejuser@fnord.comm',
              'contact.email.command mail -s "Munin Notification for ${var:host}" lingweb@shh.mpg.de',
              use_sudo=True)

    # Update host tree:
    if not files.contains(MUNIN_CFG, host_tree):
        files.append(MUNIN_CFG, host_tree, use_sudo=True)

    # Write apache24 config:
    # TODO: Check permissions of file.
    sudo_upload_template('apache24.conf', '/etc/munin/apache24.conf')

    # Set URLs for HTTP monitoring:
    sudo('touch /etc/munin/plugin-conf.d/zcustom')
    files.append('/etc/munin/plugin-conf.d/zcustom', app_watchlist, use_sudo=True)

    for s in ['munin-node', 'apache2']:
        service.restart(s)
