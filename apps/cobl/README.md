# CoBL

## Tasks

### Deploying code updates

Run
```bash
fab deploy:production
```
making sure not to recreate the database.


### Deploying the app to a new server

1. Run
   ```bash
   fab shutdown:production
   ```
   on the current production installation.
2. Edit, commit and push `apps.ini` switching the production setting to
   the new server.
3. Run
   ```bash
   fab deploy:production
   ```
   making sure to (re)create the database (from the dump that has been created
   when running `shutdown`).
