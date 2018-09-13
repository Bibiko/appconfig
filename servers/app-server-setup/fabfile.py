import os

from fabric.api import task, run
from fabric.contrib import files
from fabtools import service, deb, require
from fabtools import user as fabuser

USERS = ['robert', 'chrzyki', 'bibiko']
SSHD_CFG = '/etc/ssh/sshd_config'
POSTFIX_CFG = '/etc/postfix/main.cf'
MUNIN_CFG = '/etc/munin/munin-node.conf'
PKGS = ['language-pack-en-base', 'postfix', 'libsasl2-modules', 'bsd-mailx']


def add_user(users):
    for user in users:
        key_path = os.path.join(os.path.dirname(__file__),
                                '../ssh_key_' + user + '.pub')

        if not fabuser.exists(user):
            fabuser.create(user, password='changeme', shell='/bin/bash')

            try:
                fabuser.modify(user, ssh_public_keys=key_path)
            except FileNotFoundError:
                pass


def add_user_to_sudo(users):
    for user in users:
        fabuser.modify(user, group='sudo')


def change_authentication_method(sshd_cfg):
    files.sed(sshd_cfg, '#PasswordAuthentication yes',
              'PasswordAuthentication no', use_sudo=True)

    service.restart('sshd')


def install_packages(pkgs, postfix_cfg):
    hostname = run('hostname')
    destination_cfg = '%s.clld.org, %s, localhost.localdomain, localhost', \
                      (hostname, hostname)

    deb.preseed_package('postfix', {
        'postfix/main_mailer_type': ('select', 'Internet Site'),
        'postfix/mailname': ('string', hostname + '.clld.org'),
        'postfix/destinations': ('string', destination_cfg),
    })

    deb.install(pkgs)

    def fix_postfix_cfg():
        files.sed(postfix_cfg, 'myhostname = ', 'myhostname = '
                  + hostname + '.gwdg.de', use_sudo=True)

    fix_postfix_cfg()


def setup_munin_node(munin_cfg):
    hostname = run('hostname')

    key_path = os.path.join(os.path.dirname(__file__),
                            '../ssh_key_munin_node.pub')

    require.deb.packages(['munin-node'])

    require.users.user(
        'dlce-munin-node',
        shell='/bin/bash',
        system=True,
        ssh_public_keys=key_path)

    def fix_munin_cfg():
        files.sed(munin_cfg, '#host_name localhost.localdomain',
                  'host_name ' + hostname + '.clld.org', use_sudo=True)

    fix_munin_cfg()

    service.restart('munin-node')


@task
def setup_server():
    # TODO: Test mail setup (i.e. send test mail).
    # TODO: If a host is migrated, update SSH key on Munin master.

    add_user(USERS)
    add_user_to_sudo(USERS)
    change_authentication_method(SSHD_CFG)
    install_packages(PKGS, POSTFIX_CFG)
    setup_munin_node(MUNIN_CFG)
