# NEW-IMAGING: frisbee PXE image with AHCI support

Status (2025-10-15): images **built, NOT tested on hardware**.

## What the image is

* `irfs-pxefrisbee*.igz` = gzip'd **cpio newc** archive used as the initramfs
  of the pxefrisbee boot (`pxelinux.cfg/pxefrisbee`: `KERNEL linux-notis`, `initrd=irfs-pxefrisbee.igz`)
* userland is a debian-installer initrd (busybox + udev 204 + `anna`, `hw-detect`...),
  with `usr/sbin/frisbee`, `usr/bin/imagezip`, `imageunzip` (static emulab binaries,
  see `../frisbee-binaries-inria/`)
* boot: `/init` -> busybox init -> `/etc/init.d/rcS` -> `rcS.actual` (dhcp on `control=`, syslogd, `telnetd -l /bin/ash`)
* the **kernel is a separate file** in /tftpboot; the image only carries its modules
  under `/lib/modules/<version>/`

## Why AHCI did not work

`linux-notis` is stock Ubuntu `3.13.0-37-generic`. In that kernel `libata`, `ata_piix`
and `sd` are built in (no disk module appears in `lsmod`; `sda` shows up at t=1s),
but `ahci` + `libahci` are **modules** and had been pruned from the image.
In IDE mode the controller (Haswell, `8086:8c00`, class 0x0101) is driven by `ata_piix`;
in AHCI mode (class 0x0106) only `ahci` binds, which was missing -> no `/dev/sda`.

## Artefacts

| file | what | sha1 |
|---|---|---|
| `irfs-pxefrisbee.igz` | production image (July 2024), unchanged | 4e7fa62c... |
| `irfs-pxefrisbee-ahci.igz` | **A**: same image + `ahci.ko`/`libahci.ko`, to be used with `linux-notis` | 7453466b... |
| `linux-notis` | Ubuntu 3.13.0-37-generic bzImage (as in production) | 09f2a99b... |
| `irfs-pxefrisbee-ahci-k44.igz` | **B**: same userland, modules of Ubuntu 4.4.0-142 (xenial), pairs with kernel below | f6114b96... |
| `linux-ubuntu-4.4.0-142-generic` | Ubuntu xenial `vmlinuz`, for B | b35cb510... |

For both A and B, `rcS.actual` gets `modprobe -q ahci` (udev should also autoload it by modalias).
In B, `libata`, `ata_piix`, `scsi_mod`, `sd_mod` are likewise built in (checked in `modules.builtin`), only `ahci` is a module.

## How it was done (on `distrait`, Fedora 43, as root, in `/tmp/frisbee-build.*`)

No debian tooling needed: `ar`, `tar`, `cpio`, `gzip`, `depmod` are enough.

### A: patch the current image

```bash
W=$(mktemp -d /tmp/frisbee-build.XXXXXX); cd $W
# irfs-pxefrisbee.igz and linux-notis copied here beforehand
curl -fsSLO https://launchpad.net/ubuntu/+archive/primary/+files/linux-image-3.13.0-37-generic_3.13.0-37.64_amd64.deb
# NOTE: archive.ubuntu.com / old-releases return 404 for this one; launchpad has it

mkdir deb && (cd deb && ar x ../linux-image-*.deb && tar xf data.tar.bz2)
modinfo -F vermagic deb/lib/modules/3.13.0-37-generic/kernel/drivers/ata/ahci.ko
#   -> 3.13.0-37-generic SMP mod_unload modversions   (matches kernel)

mkdir root && (cd root && gzip -dc ../irfs-pxefrisbee.igz | cpio -idm)
K=3.13.0-37-generic
mkdir -p root/lib/modules/$K/kernel/drivers/ata
cp deb/lib/modules/$K/kernel/drivers/ata/{ahci,libahci}.ko root/lib/modules/$K/kernel/drivers/ata/
depmod -b root $K          # regenerates modules.dep(.bin), alias, symbols
```

`depmod` also truncates `modules.builtin.bin` and `modules.devname` (no text
`modules.builtin` in the tree), so restore those two files from the original
image, and remove the empty `modules.builtin.alias.bin`/`modules.weakdep` it adds.

Edit `root/etc/init.d/rcS.actual`, before the `# default control interface` block:

```sh
# AHCI-mode SATA controllers need this module (ata_piix/libata/sd are built into the kernel)
modprobe -q ahci
```

Repack (note `-R 0:0`, the tree was previously owned by a user):

```bash
(cd root && find . | cpio -o -H newc -R 0:0 --quiet | gzip -9) > irfs-pxefrisbee-ahci.igz
```

### B: same userland, newer kernel

```bash
curl -fsSLO http://archive.ubuntu.com/ubuntu/pool/main/l/linux/linux-image-4.4.0-142-generic_4.4.0-142.168_amd64.deb
mkdir k44 && (cd k44 && ar x ../linux-image-4.4.0-142-*.deb && tar xf data.tar.*)
K=4.4.0-142-generic
cp -a root rootB && rm -rf rootB/lib/modules/3.13.0-37-generic
mkdir -p rootB/lib/modules/$K
cp -a k44/lib/modules/$K/{kernel,modules.order,modules.builtin} rootB/lib/modules/$K/
# prune to save space: gpu sound media infiniband staging bluetooth video
depmod -b rootB $K
(cd rootB && find . | cpio -o -H newc -R 0:0 --quiet | gzip -9) > irfs-pxefrisbee-ahci-k44.igz
cp k44/boot/vmlinuz-$K linux-ubuntu-$K
```

## Testing (to do, by hand)

Sample `pxelinux.cfg` stanza for A (copy `pxefrisbee`, change names):

```
DEFAULT linux
LABEL linux
KERNEL linux-notis
APPEND root=/dev/ram0 rw ramdisk_size=131072 initrd=irfs-pxefrisbee-ahci.igz biosdevname=0 control=eth0 ...
```

and for B: `KERNEL linux-ubuntu-4.4.0-142-generic` + `initrd=irfs-pxefrisbee-ahci-k44.igz`.

Push: `rsync -ai <files> root@preplab.pl.sophia.inria.fr:/tftpboot/`.

On an AHCI-configured node, via telnet: `lsmod | grep ahci`, `dmesg | grep -i ahci`,
`ls /dev/sd*`, then `imagezip -o -z1 /dev/sda - | ...` / a rhubarbe save + load.
Also check it still works on an IDE-mode node (non-regression).

## Known caveats

* **untested**; B additionally changes the kernel (4.4 with udev 204 userland from 2014: expected to work, not verified).
* the stock tree has `dev/null` as a regular file (73 bytes) - inherited from earlier repacks on macOS; devtmpfs is mounted by the kernel so it is harmless in practice, but worth fixing at next rebuild (`mknod`, needs root).
* a rebuild on macOS (as in README.md) loses device nodes/ownership; build on Linux as root.
