# frisbee PXE stacks, and AHCI support

Status as of 2026-10-19. The work described here was done in October 2026 to get rid of
the need to switch node BIOS to IDE mode.

## The 4 stacks

A *stack* is a pxelinux config in `pxelinux.cfg/` that pairs one kernel with one initramfs.
The config name is the stack name:

| stack (`pxelinux.cfg/…`) | kernel | initramfs | AHCI | status |
|---|---|---|---|---|
| `pxefrisbee-k313` | `linux-ubuntu-3.13.0-37-generic` | `irfs-pxefrisbee-k313.igz` | **no** (BIOS must be in IDE mode) | the historical stack, in production until now |
| `pxefrisbee-k313-ahci` | `linux-ubuntu-3.13.0-37-generic` | `irfs-pxefrisbee-k313-ahci.igz` | yes (and IDE too) | tested OK on AHCI node; upload noticeably faster |
| `pxefrisbee-k44` | `linux-ubuntu-4.4.0-142-generic` | `irfs-pxefrisbee-k44.igz` | yes (and IDE too) | tested OK: `rload` and save both fine |
| `pxefrisbee-k70` | `linux-ubuntu-7.0.0-38-generic` | `irfs-pxefrisbee-k70.igz` | yes (and IDE too) | trials OK, being tested deeper |

Notes:

* `k313-ahci`, `k44` and `k70` all carry the AHCI driver; they only differ by kernel.
  `k313-ahci` is a strict superset of `k313` (same kernel, two more modules + one `modprobe`),
  so `k313` is only kept as a fallback to the exact previous behaviour.
* Older names for the same things, which may show up in notes, logs or git history:
  `linux-notis` = `linux-ubuntu-3.13.0-37-generic`; "option A" = `k313-ahci`;
  "option B" = `k44`; "option C" = `k70`; plain `pxefrisbee` (config) = `pxefrisbee-k313`;
  initramfs files were `irfs-pxefrisbee.igz` (= `-k313`), `irfs-pxefrisbee-ahci.igz` (= `-k313-ahci`),
  `irfs-pxefrisbee-ahci-k44.igz` (= `-k44`) and `irfs-pxefrisbee-ahci-k70.igz` (= `-k70`).
* Naming rule: stack `X` = config `pxelinux.cfg/pxefrisbee-X` = initramfs `irfs-pxefrisbee-X.igz`;
  kernels are named after the Ubuntu package they come from (`linux-ubuntu-<uname -r>`).
* `irfs-pxefrisbee.v0.igz` is the 2015 original (320 MB unpacked, with ruby/OMF); kept for reference only.

### How rhubarbe picks a stack

For a `load`/`save`, rhubarbe (`rhubarbe/node.py`, `manage_nextboot_symlink`) creates
`pxelinux.cfg/01-<mac-with-dashes>` as a symlink to the config named by the
`[pxelinux] frisbee_image` setting of `rhubarbe.conf`, reboots the node, and removes
the symlink once the node's telnet is up (so the following reboot goes to `pxelinux.cfg/default`,
which chain-loads the hard drive).

**The stacks were renamed, so there is no longer a config called plain `pxefrisbee`:
`frisbee_image` in `rhubarbe.conf` must name one of the 4 stacks above**
(this is being handled on the rhubarbe side).

To try a stack by hand on one node without touching rhubarbe's setting:

```bash
cd /tftpboot/pxelinux.cfg
ln -s pxefrisbee-k70 01-00-03-1d-0e-75-a9    # the node's control MAC; then reboot it
# afterwards, remove the symlink if rhubarbe did not
```

## What the images are

* `irfs-*.igz` = gzip'd **cpio newc** archive used as initramfs
* userland is a debian-installer initrd (busybox + udev 204 + `anna`, `hw-detect`…), from the OMF6 / NITOS days,
  with `usr/sbin/frisbee`, `usr/bin/imagezip`, `imageunzip` (static emulab binaries,
  see `../frisbee-binaries-inria/`)
* boot: `/init` -> busybox init -> `/etc/init.d/rcS` -> `rcS.actual` (dhcp on `control=`, syslogd, `telnetd -l /bin/ash`);
  rhubarbe then telnets in and runs `frisbee` / `imagezip`
* the **kernel is a separate file** loaded by pxelinux; the initramfs only carries its modules
  under `/lib/modules/<version>/` — so **kernel and initramfs of a stack must match exactly**
  (same `uname -r`), which is what the stack configs guarantee

## Why AHCI did not work

`linux-ubuntu-3.13.0-37-generic` is stock Ubuntu `3.13.0-37-generic`. In that kernel `libata`, `ata_piix`
and `sd` are built in (no disk module appears in `lsmod`; `sda` shows up at t=1s),
but `ahci` + `libahci` are **modules**, and had been pruned from the initramfs.
In IDE mode the controller (Haswell, `8086:8c00`, class 0x0101) is driven by `ata_piix`;
in AHCI mode (class 0x0106) only `ahci` binds, which was missing -> no `/dev/sda`.

The fix in all 3 AHCI stacks is the same: ship `ahci.ko` + `libahci.ko` (with a regenerated
`modules.dep`), and add `modprobe -q ahci` to `rcS.actual` (udev should also autoload it by modalias).
In the 4.4 and 7.0 kernels too, `ata_piix`, `sd` are built in and only `ahci` is a module,
so IDE mode keeps working exactly as before.

## Checksums (sha1)

| file | sha1 |
|---|---|
| `irfs-pxefrisbee-k313.igz` | `4e7fa62c…` |
| `irfs-pxefrisbee-k313-ahci.igz` | `7453466b…` |
| `irfs-pxefrisbee-k44.igz` | `f6114b96…` |
| `irfs-pxefrisbee-k70.igz` | `7e8198d4…` |
| `irfs-pxefrisbee.v0.igz` | `39a56a2e…` |
| `linux-ubuntu-3.13.0-37-generic` | `09f2a99b…` |
| `linux-ubuntu-4.4.0-142-generic` | `b35cb510…` |
| `linux-ubuntu-7.0.0-38-generic` | `7adbf624…` |

## How the images were built

Done on `distrait` (Fedora 43, as root, in `/tmp/frisbee-build.*`). Building on macOS is not
an option (device nodes/ownership, `depmod`). No debian tooling is needed: `ar`, `tar`, `cpio`,
`gzip`, `depmod` (and `unzstd` for k70) are enough. Starting point is the unpacked
`irfs-pxefrisbee-k313.igz`:

```bash
mkdir root && (cd root && gzip -dc ../irfs-pxefrisbee-k313.igz | cpio -idm)
```

### k313-ahci: patch the current image

```bash
W=$(mktemp -d /tmp/frisbee-build.XXXXXX); cd $W
# irfs-pxefrisbee-k313.igz copied here beforehand
curl -fsSLO https://launchpad.net/ubuntu/+archive/primary/+files/linux-image-3.13.0-37-generic_3.13.0-37.64_amd64.deb
# NOTE: archive.ubuntu.com / old-releases return 404 for this one; launchpad has it

mkdir deb && (cd deb && ar x ../linux-image-*.deb && tar xf data.tar.bz2)
modinfo -F vermagic deb/lib/modules/3.13.0-37-generic/kernel/drivers/ata/ahci.ko
#   -> 3.13.0-37-generic SMP mod_unload modversions   (matches the kernel)

K=3.13.0-37-generic
mkdir -p root/lib/modules/$K/kernel/drivers/ata
cp deb/lib/modules/$K/kernel/drivers/ata/{ahci,libahci}.ko root/lib/modules/$K/kernel/drivers/ata/
depmod -b root $K          # regenerates modules.dep(.bin), alias, symbols
```

`depmod` also truncates `modules.builtin.bin` and `modules.devname` (there is no text
`modules.builtin` in the tree), so restore those two files from the original
image, and remove the empty `modules.builtin.alias.bin`/`modules.weakdep` it adds.

Edit `root/etc/init.d/rcS.actual`, before the `# default control interface` block:

```sh
# AHCI-mode SATA controllers need this module (ata_piix/libata/sd are built into the kernel)
modprobe -q ahci
```

Repack (`-R 0:0`: the tree used to be owned by a user):

```bash
(cd root && find . | cpio -o -H newc -R 0:0 --quiet | gzip -9) > irfs-pxefrisbee-k313-ahci.igz
```

The kernel is unchanged: `linux-ubuntu-3.13.0-37-generic`.

### k44: same userland, Ubuntu 16.04 kernel 4.4.0-142

```bash
curl -fsSLO http://archive.ubuntu.com/ubuntu/pool/main/l/linux/linux-image-4.4.0-142-generic_4.4.0-142.168_amd64.deb
mkdir k44 && (cd k44 && ar x ../linux-image-4.4.0-142-*.deb && tar xf data.tar.*)
K=4.4.0-142-generic
cp -a root rootB && rm -rf rootB/lib/modules/3.13.0-37-generic    # root = k313-ahci tree, with the rcS.actual edit
mkdir -p rootB/lib/modules/$K
cp -a k44/lib/modules/$K/{kernel,modules.order,modules.builtin} rootB/lib/modules/$K/
# prune to save space: gpu sound media infiniband staging bluetooth video
depmod -b rootB $K
(cd rootB && find . | cpio -o -H newc -R 0:0 --quiet | gzip -9) > irfs-pxefrisbee-k44.igz
cp k44/boot/vmlinuz-$K linux-ubuntu-$K
```

### k70: same userland, Ubuntu 26.04 "resolute" kernel 7.0.0-38

Differences from k44 that matter:

* two debs: `linux-image-unsigned-7.0.0-38-generic` (vmlinuz) and `linux-modules-7.0.0-38-generic`
  (from `resolute-updates`, both `7.0.0-38.38`); the `.deb` data member is a plain `data.tar`
* modules live under `usr/lib/modules/` (usrmerge) and are **zstd-compressed** (`.ko.zst`);
  the image's modprobe is busybox's, which cannot read them, so they are decompressed
  (`unzstd`) before `depmod -b`
* kernel config (from `boot/config-*`): `ATA_PIIX=y`, `BLK_DEV_SD=y`, `PTP_1588_CLOCK=y`, `PPS=y`
  built in; `SATA_AHCI`, `IGB`, `E1000E`, `R8169` are modules; `DEVTMPFS(_MOUNT)=y`; `RD_GZIP=y`
* the module tree is 300 MB unpacked, so it is **pruned hard**: gpu, media, sound, wireless, bluetooth,
  infiniband, staging, usb, hid, input, scsi, md, fs, netfilter, and all ethernet vendors except
  intel, realtek, broadcom, atheros, 3com, amd, dec, via, sis, nvidia, marvell, 8390, mellanox
  (143 MB left; image is 67 MB). **If a node type has a NIC outside that list, restore its directory** (and rerun `depmod`)
* `rcS.actual` is unchanged (`modprobe -q ahci`)

```bash
K=7.0.0-38-generic; U=http://archive.ubuntu.com/ubuntu/pool/main/l/linux
curl -fsSLO $U/linux-image-unsigned-7.0.0-38-generic_7.0.0-38.38_amd64.deb
curl -fsSLO $U/linux-modules-7.0.0-38-generic_7.0.0-38.38_amd64.deb
mkdir img mod
(cd img && ar x ../linux-image-unsigned-*.deb && tar xf data.tar)
(cd mod && ar x ../linux-modules-*.deb && tar xf data.tar)
cp -a root rootC && rm -rf rootC/lib/modules/3.13.0-37-generic
D=rootC/lib/modules/$K; mkdir -p $D
cp -a mod/usr/lib/modules/$K/{kernel,modules.builtin,modules.builtin.modinfo,modules.order} $D/
find $D -name '*.ko.zst' -exec unzstd -q --rm {} +
# prune (see list above), then
depmod -b rootC $K
(cd rootC && find . | cpio -o -H newc -R 0:0 --quiet | gzip -9) > irfs-pxefrisbee-k70.igz
cp img/boot/vmlinuz-$K linux-ubuntu-$K
```

If the NIC is not called `eth0` on some hardware with this kernel, add `net.ifnames=0`
next to `biosdevname=0` in the `APPEND` line of `pxefrisbee-k70` (it was not needed on the nodes tried so far).

Failure triage order if a stack does not work: kernel does not boot (pxelinux/bzImage) ->
no network (module missing, NIC naming) -> no `/dev/sda` -> telnet.

## Deploying and testing

```bash
rsync -ai irfs-* linux-* root@preplab.pl.sophia.inria.fr:/tftpboot/
rsync -ai pxelinux.cfg/pxefrisbee-* root@preplab.pl.sophia.inria.fr:/tftpboot/pxelinux.cfg/
```

(same for production, with the right host). On a node booted in a given stack, via telnet:
`uname -r`, `lsmod | grep ahci`, `dmesg | grep -i ahci`, `ls /dev/sd*`, then a rhubarbe `save`
and `load`. Do it on both AHCI-mode and IDE-mode nodes (non-regression).

## Known caveats

* the stock tree has `dev/null` as a regular file (73 bytes) - inherited from earlier repacks on macOS;
  devtmpfs is mounted by the kernel so it is harmless in practice, but worth fixing at the next
  rebuild (`mknod`, needs root).
* the userland (udev 204, 2014 busybox) is old; it works with all 3 kernels so far, but this is
  empirical, not guaranteed for other hardware.
* k44 and k70 are Ubuntu binary kernels fetched as-is; no patches, so security updates are only a
  matter of rebuilding with a newer package version.
* a rebuild on macOS loses device nodes/ownership; build on Linux as root.
