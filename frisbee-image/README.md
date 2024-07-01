# tweaking the frisbee image

## context

* when: on 2024 Jul 1
* why: fit01 is misbehaving and e don't understand why
* what: add a getty process to the frisbee image so that one can log in and see what's going on

## steps to rebuild

### starting from this release

```bash
ls -l *z; sha1sum *z
-rwxr-xr-x 1 tparment diana 71459051 Jul  1 09:17 irfs-pxefrisbee.igz
39a56a2e826b50249143e66499c2083769f3780b  irfs-pxefrisbee.igz
```

that for safety we copy first as

```bash
cp irfs-pxefrisbee.igz irfs-pxefrisbee.v0.igz
```

### unpack the image

```bash
mkdir root; gzip -dc irfs-pxefrisbee.igz | (cd root; cpio -diu)
```

### patch `/etc/inittab`

* /bin/bash is non-existent in this image; so we go for 3 instances of /bin/sh on Alt-F2 .. Alt-F4
* turn off this line that only clobbers /var/log/messages

```bash
# tty4::respawn:/usr/bin/tail -f /var/log/syslog
```

### misc tweaks and clean up

#### `/etc/init.d/rcS.actual`

* removed super-old OMF-related stuff that was commented off anyway
* added -S option to `udhcpc` so we get more logs about that process

#### leftovers of omf/ruby

removed the following directories, that reduced the image size
from 321M to 101M !

```bash
root//usr/lib/ruby
root//usr/sbin/omf-resctl-5.4
root//usr/share/omf-common-5.4
root//usr/bin/ruby*
root//usr/include/ruby-1.9.1
root//usr/share/man/man1/ruby.1
root/usr/share/ri/
```

#### emacs backups

* removed a couple emacs backup (files in `*~`)

### rewrap the image

```bash
(cd root; find . | cpio -o -H newc | gzip -9) > irfs-pxefrisbee.igz
```

## push in production

```bash
rsync -ai irfs-pxefrisbee.igz root@distrait.pl.sophia.inria.fr:/tftpboot/irfs-pxefrisbee.igz
rsync -ai irfs-pxefrisbee.igz root@faraday.inria.fr:/tftpboot/irfs-pxefrisbee.igz
```

so we end up with

```bash
root@distrait /tftpboot (main) # ls -l irfs*
-rwxr-xr-x 1   15010  200036 36061838 Jul  1 10:49 irfs-pxefrisbee.igz
-rwxr-xr-x 1 dnsmasq dnsmasq 71459051 May 15  2015 irfs-pxefrisbee.v0.igz
root@distrait /tftpboot (main) # sha1sum irfs*
4e7fa62ca1c7572d4cefca716f077b893100643b  irfs-pxefrisbee.igz
39a56a2e826b50249143e66499c2083769f3780b  irfs-pxefrisbee.v0.igz
```
