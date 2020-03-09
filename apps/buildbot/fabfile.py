from fabric.api import env, sudo
from fabtools import require, system, python
from fabtools.require import git

from appconfig.tasks import task_app_from_environment, init
from appconfig.tasks.deployment import require_venv

init()


@task_app_from_environment
def deploy(app):
    assert system.distrib_id() == "Ubuntu"
    assert env.environment == "production"

    require.deb.packages(app.require_deb + ["libcairo2", "python3-venv"])
    require.users.user(app.name, create_home=True, shell="/bin/bash")

    # Test and production instances are publicly accessible over HTTPS.
    #    letsencrypt.require_certbot()
    #    letsencrypt.require_cert(env.host)
    #    letsencrypt.require_cert(app)

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
        contents="HOST='141.5.108.108'",
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

    with python.virtualenv(str(app.venv_dir)):
        sudo("buildbot-worker stop " + str(app.home_dir / "worker"), user="buildbot")
        sudo("buildbot create-master -c config.py " + str(app.home_dir / "master"), user="buildbot")
        sudo("buildbot start " + str(app.home_dir / "master"), user="buildbot", warn_only=True)
        sudo(
            "buildbot-worker create-worker "
            + str(app.home_dir / "worker")
            + " "
            + "localhost worker pass",
            user="buildbot",
        )
        sudo(
            "buildbot-worker start " + str(app.home_dir / "worker"), user="buildbot", warn_only=True
        )


#   require_nginx(dict(app=app))

# start.execute_inner(app)
# check(app)
#   if env.environment == 'production':
#       systemd.enable(app, pathlib.Path(os.getcwd()) / 'systemd')
