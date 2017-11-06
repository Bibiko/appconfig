# varnish.py - install, configure, and run varnish cache

from __future__ import unicode_literals

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
    - create /etc/varnish/sites.vcl
      (and require it to contain the correct include!)
    - create /etc/varnish/sites/
    - create /etc/varnish/sites/{app.name}.vcl
    - /etc/init.d/varnish restart
    - adapt nginx site config
    - /etc/init.d/nginx reload
    """
    require.deb.package('varnish')

    deployment.sudo_upload_template('varnish', dest='/etc/default/varnish')
    deployment.sudo_upload_template('varnish_main.vcl', dest='/etc/varnish/main.vcl')
    include_line = 'include "%s";\n' % app.varnish_site
    deployment.upload_or_append('/etc/varnish/sites.vcl', contents=include_line, use_sudo=True)

    require.directory(str(app.varnish_site.parent), use_sudo=True)
    deployment.sudo_upload_template('varnish_site.vcl', dest=str(app.varnish_site),
                                    app_name=app.name, app_port=app.port,
                                    app_domain=app.domain)

    service.restart('varnish')

    context = deployment.template_context(app.replace(port=6081))
    deployment.sudo_upload_template('nginx-app.conf', dest=str(app.nginx_site),
                                    context=context, SITE=True)
    service.reload('nginx')


@task_app_from_environment('production')
def uncache(app):  # pragma: no cover
    context = deployment.template_context(app)
    deployment.sudo_upload_template('nginx-app.conf', dest=str(app.nginx_site),
                                    context=context, SITE=True)
    service.reload('nginx')
