# see README.md for instructions

RSYNC_COMMON = -rtlpi
RSYNC_COND_DRY_RUN    := $(if $(findstring n,$(MAKEFLAGS)),--dry-run,)
RSYNC_OPTS = $(RSYNC_COMMON) $(RSYNC_COND_DRY_RUN)

all:
	echo pick one of the push- targets

push-conf:
	+rsync $(RSYNC_OPTS) switch-{c007,data,control,reboot,radio}.conf root@faraday.inria.fr:/tftpboot/

push-dnsmasq:
	+rsync $(RSYNC_OPTS) dnsmasq.conf.faraday root@faraday.inria.fr:/etc/dnsmasq.conf
