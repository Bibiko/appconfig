import os

from fabric.api import task, env
from fabric.contrib.console import confirm
from fabtools import user as fabuser

from appconfig import APPS

env.hosts = APPS.hostnames


@task
def add_key(user='', key=''):
    if not user:
        raise ValueError("Username cannot be empty.")

    if confirm("Add key/user to: " + env.host_string + "?"):
        key_path = os.path.join(os.path.dirname(__file__), key)

        if not fabuser.exists(user):
            fabuser.create(user, password='changeme')

        try:
            fabuser.modify(user, ssh_public_keys=key_path)
        except FileNotFoundError:
            print("Could not find SSH key at the specified location.")
