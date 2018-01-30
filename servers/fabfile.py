from fabric.api import task, sudo


@task
def ls():
    """list installed clld apps"""
    sudo('supervisorctl avail')
    sudo('psql -l', user='postgres')

