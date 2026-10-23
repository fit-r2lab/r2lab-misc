# stupidest mistakes so far on `etourdi`

## one glitch seen on `etourdi` wrt `firewalld`

One day after a power outage:

* `etourdi` failed to restart on its own once power was back on
* and, after we manually rebooted it, `etourdi`'s `iptables` were off somehow

So I have reconfigured the BIOS so that `etourdi` will now come back on in case of a power outage.

Googling the second issue a bit brought up this:

* https://unix.stackexchange.com/questions/339465/how-to-disable-firewalld-and-keep-it-that-way
* so I followed that advice and just did

   `dnf remove firewalld`

Which seems to have done it once and for good.

## `dnsmasq` refused to start

One day I ran a harmless rhubarbe command in `/etc/dnsmasq.d`. This had the
result of creating a file named `/etc/dnsmasq.d/rhubarbe.log`.

Next time `dnsmasq` tried to run, it complained about a syntax error in this file, **refused to start**; no DNS, ouch ..

Took me 1 hour to figure that out.

I believe after that `rhubarbe.log` now always gets created in the homedir...
