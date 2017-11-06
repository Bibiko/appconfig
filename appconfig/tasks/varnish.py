# varnish.py - install, configure, and run varnish cache

from __future__ import unicode_literals

import os

from fabric.api import run
from fabric.contrib import files
from fabtools import require, service

from . import task_app_from_environment
from . import deployment  # FIXME

__all__ = ['cache', 'uncache']


@task_app_from_environment('production')
def cache(app):  # pragma: no cover
    """require an app to be put behind varnish

    - apt-get install varnish
    - create /etc/default/varnish
    - create /etc/varnish/main.vcl
    - create /etc/varnish/sites/
    - create /etc/varnish/sites/{app.name}.vcl
    - create /etc/varnish/sites.vcl
      (and require it to contain the correct include!)
    - /etc/init.d/varnish restart
    - adapt nginx site config
    - /etc/init.d/nginx reload
    """
    require.deb.package('varnish')

    deployment.sudo_upload_template('varnish', dest='/etc/default/varnish')
    deployment.sudo_upload_template('varnish_main.vcl', dest='/etc/varnish/main.vcl')

    require.directory(str(app.varnish_site.parent), use_sudo=True)
    deployment.sudo_upload_template('varnish_site.vcl', dest=str(app.varnish_site),
                                    app_name=app.name, app_port=app.port,
                                    app_domain=app.domain)

    sites = run('find %s -mindepth 1 -maxdepth 1 -type f ' % app.varnish_site.parent,
                combine_stderr=False).splitlines()
    includes = ''.join('include "%s";\n' % s for s in sites)
    require.file('/etc/varnish/sites.vcl', contents=includes, use_sudo=True, mode='644')    

    service.restart('varnish')

    _require_nginx(app)


@task_app_from_environment('production')
def uncache(app):  # pragma: no cover
    _require_nginx(app)


def _require_nginx(app, varnish_port=6081):
    ctx = deployment.template_context(app.replace(port=varnish_port))
    deployment.require_nginx(ctx,
                             default_site=app.nginx_default_site, site=app.nginx_site,
                             location=app.nginx_location, logrotate=app.logrotate,
                             venv_dir=app.venv_dir,
                             htpasswd_file=app.nginx_htpasswd, htpasswd_user=app.name)
    service.reload('nginx')
