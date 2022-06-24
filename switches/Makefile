RSYNC_COMMON = -rtlpi
RSYNC_COND_DRY_RUN    := $(if $(findstring n,$(MAKEFLAGS)),--dry-run,)
RSYNC_OPTS = $(RSYNC_COMMON) $(RSYNC_COND_DRY_RUN)

all:
	echo pick one of the push- targets

# once you have made a make push you can run from the switch something like e.g.
#
# copy tftp://192.168.4.100/switch-c007.conf startup-config
# copy tftp://192.168.4.100/switch-c007.conf running-config
#
# copy tftp://192.168.4.100/switch-data.conf startup-config
# copy tftp://192.168.4.100/switch-data.conf running-config
#
# copy tftp://192.168.4.100/switch-control.conf startup-config
# copy tftp://192.168.4.100/switch-control.conf running-config
#
# copy tftp://192.168.4.100/switch-reboot.conf startup-config
# copy tftp://192.168.4.100/switch-reboot.conf running-config
#
# copy tftp://192.168.4.100/switch-radio.conf startup-config
# copy tftp://192.168.4.100/switch-radio.conf running-config
#
# reload

push-conf:
	+rsync $(RSYNC_OPTS) switch-*.conf root@faraday.inria.fr:/tftpboot/

push-dnsmasq:
	+rsync $(RSYNC_OPTS) dnsmasq.conf.faraday root@faraday.inria.fr:/etc/dnsmasq.conf
