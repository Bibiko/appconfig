# appconfig

Scripted deployment of dlce webapps

[![Build Status](https://travis-ci.org/shh-dlce/appconfig.svg?branch=master)](https://travis-ci.org/shh-dlce/appconfig)


## Deploying an app

### Deploying new code

All new code must be pushed to the `app` repository on GitHub.
While no local installation of the app or a local database are required, it is recommended to run the app's tests
before deployment.

1. Activate the "remote control":
```
$ workon appconfig
```

2. Change into the config directory for the app:
```
$ cd appconfig/apps/<app>
```

3. Run the `deploy` task, passing a deployment mode as argument.
There are three deployment modes:
- `production`: The app is deployed
  - under its specified domain
  - using a separate nginx site
  - forcing HTTPS.
- `test`: The app is deployed
  - mounted at the `app.name` path on the default server
  - forcing HTTPS (for the default server)
- `staging`: The app is deployed
  - under its specified domain
  - using a separate nginx site
  - serving via HTTP

Thus, `production` and `test` mode should only be used with the configured servers,
because otherwise retrieving the required certificates from letsencrypt will fail.

To deploy the app to a custom server, e.g. a virtualbox on the local machine, use
`staging` mode with `fab`'s `-H` option, e.g.
```
$ fab -H vbox deploy:staging
```
Answer the prompts `Recreate database?` and `Upgrade database?` in the negative.

#### Troubleshooting

Sometimes an app won't start properly after updating the code. By far the most common cause for this
are changes in requirements, leading to package version conflicts. To resolve such problems:
- Log into the the server and change to a superuser account.
- Comment out the lines in `/home/<app>/config.ini` specifying the options `workers` and `proc_name` for
  the app server. (These options are `gunicorn`-specific and won't be understood by `waitress` - which we
  want to use for debugging.)
- Start the app with `waitress` running
  ```shell script
  /usr/venvs/<app>/bin/pserve /home/<app>/config.ini
  ```
  and observe the errors reported.
- Install appropriate versions of conflicting packages running
  ```shell script
  /usr/venvs/<app>/bin/pip install ...
  ```
- Try to start again ...
- When `waitress` will start without problems, stop it, revert `config.ini` and restart `gunicorn` via `supervisor`:
  ```shell script
  supervisorctl start <app>
  ```
- To make sure everything is deployed as always (and to record the new package versions), deploy via `fab` again
  and commit and push the updated `requirements.txt`.


### Deploying new data

New data can be deployed in two ways, either via alembic migrations, altering an existing database, or by replacing
the database wholesale.
In the first case, the migration must be pushed to the app's repository on GitHub; in the second case a local app database
must be available.

As above, activate `appconfig`, change into the app's config directory and start the `deploy` task. In case of a database migration, answer `Recreate database?` in the negative and run the migrations on the host by confirming `Upgrade database?`.
For wholesale replacemement, confirm `Recreate database?`.

Note: Deploying new data implies deploying new code.


## Renewing certificates

We use certificates from [letsencrypt](https://letsencrypt.org/) to secure our
apps and servers. Since these have a fixed validity of 90 days, we have to run our
global renewal task every 30 days (since we don't know at which point in a 90 day interval a new app may have been deployed):

```bash
cd servers
fab renew_certs
```

This task loops through all configured production hosts, and upon confirmation
attempts to renew certificates for all production apps deployed on the host.


## Supported stacks

### clld (Pyramid)

TODO


### Django

Django apps are deployed in a way that is modeled closely after the deployment model for
`clld` apps. In particular:
- all Django apps must be installable python packages ...
- ... providing an `paste.app_factory` entry point.
- Apps are served by gunicorn.
- Apps are controlled using supervisord.
- Supervisor starts apps using the [`paste` option](http://docs.gunicorn.org/en/stable/run.html#paste), thus apps can access deployment specific configuration by reading the config file passed into the `paste.app_factory` function.

In addition to deployment specific config passed via `app.config` Django apps require
a [`SECRET_KEY`](https://docs.djangoproject.com/en/2.1/ref/settings/#std:setting-SECRET_KEY) setting.
Since one might not want to change this key with each deploy (which will invalidate existing sessions)
it can optionally be recreated upo deployment and is written to a file `secret_key` in `app.home`.
