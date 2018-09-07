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


### Deploying new data

New data can be deployed in two ways, either via alembic migrations, altering an existing database, or by replacing
the database wholesale.
In the first case, the migration must be pushed to the app's repository on GitHub; in the second case a local app database
must be available.

As above, activate `appconfig`, change into the app's config directory and start the `deploy` task. In case of a database migration, answer `Recreate database?` in the negative and run the migrations on the host by confirming `Upgrade database?`.
For wholesale replacemement, confirm `Recreate database?`.

Note: Deploying new data implies deploying new code.
