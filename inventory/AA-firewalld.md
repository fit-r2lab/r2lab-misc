# stupidest mistake so far on `etourdi` 

One day I ran a harmless rhubarbe command in `/etc/dnsmasq.d`. This had the result of creating a file named `/etc/dnsmasq.d/rhubarbe.log`.

Next time `dnsmasq` tried to run, it complained about a syntax error in this file, **refused to start**; no DNS, ouch ..

Took me 1 hour to figure that out.

# another glitch seen on `etourdi`

One day after a power outage:

* `etourdi` failed to restart on its own once power was back on
* and, after we manually rebooted it, `etourdi`'s `iptables` were off somehow

So I have reconfigured the BIOS so that `etourdi` will now come back on in case of a power outage.

Googling the second issue a bit brought up this:

* https://unix.stackexchange.com/questions/339465/how-to-disable-firewalld-and-keep-it-that-way
* so I followed that advice and just did

   `dnf remove firewalld`

Which seems to have done it once and for good.

# NOTES on upgrading r2labapi / plcapi

the most common mistakes are:

## pgsql crash

sometimes (and more than a few times) I have seen the DB in a weird / metastable state, where the POSTGRESQL server just crashes

this typically happens when the pgsql version bumps and I need to restore the DB from a backup

I fix that using

```bash
pg_resetwal /var/lib/pgsql/data
```

However this needs to be run as `postgres` user, so I have to do

```bash
# su - postgres
$ pg_resetwal /var/lib/pgsql/data
$ exit
```

## the UI complains about not being able to use the MySQL db

the keyword here is "MySQL" - this is a sign that the `settings.php` file is not properly patched

Hopefully this sould no longer happen; BUT if it does, check for the file

```bash
/var/www/html/sites/default/settings.php
```

which SHOULD differ from a file named `settings.php.drupal` in the same directory, and in any casse should contain this line

```php
require_once("plc_config.php");$db_url="pgsql://" . PLC_DB_USER . ":" . PLC_DB_PASSWORD . "@" . PLC_DB_HOST . ":" . PLC_DB_PORT . "/drupal";
```

this is patched by the `plewww` install script, but it's worth checking;  
this line is the one defining the DB address for drupal, and when missing it defaults to MySQL
