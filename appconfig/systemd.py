import os

from fabric.api import sudo
from fabtools import files


def upload_template(p, dest, ctx, mode='644'):
    files.upload_template(
        p.name,
        dest,
        ctx,
        use_jinja=True,
        template_dir=str(p.parent),
        use_sudo=True,
        mode=mode,
        backup=False,
        chown=True)


def enable(app, d):
    """
    Install systemd units for an app.

    Installs and enables systemd units, e.g. services and/or timers required by an app.
    Each unit is expected to be specified by a subdirectory of `d`, with files
    - `service`
    - `timer`
    - `script`

    These files are treated as Jinja tamplates, rendered and put in
    - /etc/systemd/system (for timers and services) and
    - /user/bin for scripts.

    The template context available within the files is
    - `app`: The App instance, the unit is used for
    - `script_path`: The path of the associated script on the target system.
    """
    if d.exists() and d.name == 'systemd':
        for unit in d.iterdir():
            ctx = dict(app=app, osenv=os.environ)
            script = unit / 'script'
            if script.exists():
                ctx['script_path'] = script_path = '/usr/bin/{0}-{1}'.format(app.name, unit.name)
                upload_template(script, script_path, ctx, mode='755')

            enable = 'service'
            for name in ['service', 'timer']:
                if name == 'timer':
                    enable = name
                p = unit / name
                if p.exists():
                    upload_template(
                        p, '/etc/systemd/system/{0}-{1}.{2}'.format(app.name, unit.name, name), ctx)
            sudo('systemctl start {0}-{1}.{2}'.format(app.name, unit.name, enable))
            sudo('systemctl enable {0}-{1}.{2}'.format(app.name, unit.name, enable))
        sudo('systemctl daemon-reload')
