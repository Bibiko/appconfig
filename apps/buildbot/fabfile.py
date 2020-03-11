import pathlib

from fabric.api import env, sudo, shell_env
from fabtools import require, system, python
from fabtools.require import git

from appconfig import systemd
from appconfig.tasks import letsencrypt
from appconfig.tasks import task_app_from_environment, init
from appconfig.tasks.deployment import require_venv, require_nginx

init()


@task_app_from_environment
def deploy(app):
    assert system.distrib_id() == "Ubuntu"
    assert env.environment == "production"

    require.deb.packages(app.require_deb + ["libcairo2", "python3-venv"])
    require.users.user(app.name, create_home=True, shell="/bin/bash")

    with shell_env(SYSTEMD_PAGER=''):
        require.nginx.server()

    # Test and production instances are publicly accessible over HTTPS.
    letsencrypt.require_certbot()
    letsencrypt.require_cert(env.host)
    letsencrypt.require_cert(app)

    require_nginx(dict(app=app))

    git.working_copy(
        "https://github.com/cldf/cldf-buildbot.git",
        path=str(app.home_dir / "cldf-buildbot"),
        user="buildbot",
        use_sudo=True,
    )

    git.working_copy(
        "https://github.com/glottolog/glottolog.git",
        path=str(app.home_dir / "glottolog"),
        user="buildbot",
        use_sudo=True,
    )

    git.working_copy(
        "https://github.com/concepticon/concepticon-data.git",
        path=str(app.home_dir / "concepticon-data"),
        user="buildbot",
        use_sudo=True,
    )

    git.working_copy(
        "https://github.com/cldf-clts/clts.git",
        path=str(app.home_dir / "clts"),
        user="buildbot",
        use_sudo=True,
    )

    # fabtools.git.checkout() for versions

    require_venv(
        app.venv_dir, requirements=str(app.home_dir / "cldf-buildbot" / "requirements.txt")
    )

    require.directory(str(app.home_dir / "master"), owner="buildbot", use_sudo=True)
    require.directory(str(app.home_dir / "worker"), owner="buildbot", use_sudo=True)

    require.files.file(
        path=str(app.home_dir / "master" / "settings.py"),
        owner="buildbot",
        contents="HOST='buildbot.clld.org'",
        use_sudo=True,
        mode="777",
    )

    sudo(
        "cp "
        + str(app.home_dir / "cldf-buildbot" / "reposlist.json")
        + " "
        + str(app.home_dir / "master"),
        user="buildbot",
    )

    sudo(
        "cp "
        + str(app.home_dir / "cldf-buildbot" / "config.py")
        + " "
        + str(app.home_dir / "master"),
        user="buildbot",
    )

    sudo("systemctl stop buildbot-master", warn_only=True)
    sudo("systemctl stop buildbot-worker", warn_only=True)

    with python.virtualenv(str(app.venv_dir)):
        sudo("buildbot create-master -c config.py " + str(app.home_dir / "master"), user="buildbot")
        sudo(
            "buildbot-worker create-worker "
            + str(app.home_dir / "worker")
            + " "
            + "localhost worker pass",
            user="buildbot",
        )

    systemd.enable(app, pathlib.Path(__file__).parent / "systemd")
    sudo("systemctl daemon-reload", warn_only=True)
    sudo("systemctl start buildbot-master", warn_only=True)
    sudo("systemctl start buildbot-worker", warn_only=True)
