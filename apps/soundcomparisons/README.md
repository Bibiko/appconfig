
Write specific config to a separate config file
/etc/php/7.0/fpm/pool.d/wwwsoundcomparisons.conf

See
https://serverfault.com/questions/805647/override-php-fpm-pool-config-values-with-another-file

```
253c259
< access.log = /var/log/$pool.access.log
---
> ;access.log = log/$pool.access.log
355c361
< chdir = /srv/soundcomparisons/site
---
> ;chdir = /var/www
362c368
< catch_workers_output = yes
---
> ;catch_workers_output = yes
389,393d394
< env[DEPLOYED] = 'true'
< env[MYSQL_SERVER] = 'localhost'
< env[MYSQL_USER] = 'soundcomparisons'
< env[MYSQL_PASSWORD] = '...'
< env[MYSQL_DATABASE] = 'v4'
417c418
< php_admin_flag[log_errors] = on
---
> ;php_admin_flag[log_errors] = on
```



TODO:
- fix php.ini variables_order
- run bower install in js dir
