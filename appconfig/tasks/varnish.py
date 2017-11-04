# varnish.py - install, configure, and run varnish cache

"""deploy with varnish:

- apt-get install varnish
- create /etc/default/varnish
- create /etc/varnish/main.vcl
- create /etc/varnish/sites.vcl
- create /etc/varnish/sites/
  (and require it to contain the correct include!)
- create /etc/varnish/sites/{app.name}.vcl
- /etc/init.d/varnish restart
- adapt nginx site config
- /etc/init.d/nginx reload
"""

from __future__ import unicode_literals

from fabric.contrib import files
from fabtools import require, service

from . import task_app_from_environment
from . import deployment  # FIXME

__all__ = ['cache', 'uncache']

DEFAULT = """
START=yes
NFILES=131072
MEMLOCK=82000
# Default varnish instance name is the local nodename.  Can be overridden with
# the -n switch, to have more instances on a single server.
# INSTANCE=$(uname -n)
DAEMON_OPTS="-a :6081 \
             -T localhost:6082 \
             -t 3600 \
             -f /etc/varnish/main.vcl \
             -S /etc/varnish/secret \
             -s file,/var/lib/varnish/$INSTANCE/varnish_storage.bin,10G"
"""

MAIN_VCL = """
sub vcl_recv {
    set req.http.Host = regsub(req.http.Host, "^www\.", "");
    set req.http.Host = regsub(req.http.Host, ":80$", "");
}

include "/etc/varnish/sites.vcl";
"""

SITE_VCL_TEMPLATE = """
backend {app.name} {{
    .host = "127.0.0.1";
    .port = "{app.port}";
}}

sub vcl_recv {{
    if (req.http.host ~ "^{app.domain}$")  {{ set req.backend = {app.name}; }}
}}

sub vcl_fetch {{
    set beresp.ttl = 3600s;
    return(deliver);
}}
"""


@task_app_from_environment('production')
def cache(app):  # pragma: no cover
    """require an app to be put behind varnish"""
    require.deb.package('varnish')
    require.file('/etc/default/varnish', DEFAULT, use_sudo=True)
    require.file('/etc/varnish/main.vcl', MAIN_VCL, use_sudo=True)

    sites_vcl = '/etc/varnish/sites.vcl'
    site_config_dir = '/etc/varnish/sites'
    site_config = '%s/%s.vcl' % (site_config_dir, app.name)
    include = 'include "%s";' % site_config

    if files.exists(sites_vcl):
        files.append(sites_vcl, include, use_sudo=True)
    else:
        require.file(sites_vcl, include + '\n', use_sudo=True)

    require.directory(site_config_dir, use_sudo=True)
    require.file(site_config, SITE_VCL_TEMPLATE.format(app=app), use_sudo=True)
    service.restart('varnish')

    context = deployment.template_context(app.replace(port=6081))
    deployment.sudo_upload_template('nginx-app.conf', dest=app.nginx_site,
                                    context=context, SITE=True)
    service.reload('nginx')


@task_app_from_environment('production')
def uncache(app):  # pragma: no cover
    ctx = deployment.template_context(app)
    ctx['auth'], _ = deployment.http_auth(username=app.name, htpasswd_file=app.nginx_htpasswd)
    require.file(app.nginx_site, SITE_VCL_TEMPLATE.format(**ctx))
    service.reload('nginx')
