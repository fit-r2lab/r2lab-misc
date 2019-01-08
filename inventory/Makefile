# default is for the production deployment
GATEWAY  = root@faraday.inria.fr
TBNAME = r2lab

RHUBARBE_INVENTORY = /etc/rhubarbe/inventory-nodes.json

PREPLAB-HOSTNAME=etourdi

# see the prep-* targets
PREP_GATEWAY  = root@preplab.pl.sophia.inria.fr
PREP_TBNAME = r2lab-prep

# see AA-README.md

all: configure

# for when a remap occurs
# xxx todo : edit /etc/rhubarbe/rhubarbe.conf on preplab to reflect the scope of rhubarbe -a
# xxx todo : tweak faraday.sh so that it gets the default all-nodes from rhubarbe.conf
# for now I do this manually each time
production remap: all publish

.PHONY: remap production

####################
# nagios is no longer running on the gateway
publish: configure rhubarbe infra

.PHONY: all publish

SCRIPT = configure.py
SOURCE = r2lab.map

define byproducts
$(1)-rhubarbe.json $(1).dnsmasq $(1).hosts
endef

PRODUCTS         = $(call byproducts,$(TBNAME))
PREPLAB-PRODUCTS   = $(call byproducts,$(PREP_TBNAME)) r2lab-prep.spare-nodes

####################
configure: $(PRODUCTS)
$(PRODUCTS): $(SCRIPT) $(SOURCE)
	python $(SCRIPT) $(SOURCE)

$(PREPLAB-PRODUCTS): $(SCRIPT) $(SOURCE)
	python $(SCRIPT) --prep-lab $(SOURCE)
preplab-configure: $(PREPLAB-PRODUCTS)

.PHONY: configure

####################
clean:
	rm -f $(PRODUCTS) $(PREPLAB-PRODUCTS)

.PHONY: clean

####################
rhubarbe-push:  $(TBNAME)-rhubarbe.json
	rsync -vrltp $(TBNAME)-rhubarbe.json $(GATEWAY):$(RHUBARBE_INVENTORY)

rhubarbe: rhubarbe-push

.PHONY: rhubarbe rhubarbe-push

####################
infra-push: $(TBNAME).dnsmasq $(TBNAME).hosts
	rsync -rltp $(TBNAME).dnsmasq $(GATEWAY):/etc/dnsmasq.d/testbed.conf
	rsync -rltp $(TBNAME).hosts $(GATEWAY):/etc/hosts

# make sure the leases file gets cleaned up otherwise the new node may
# need to wait for *some time* before it gets served its address
# getting stuff like 192.168.3.251 instead
infra-restart:
	ssh $(GATEWAY) systemctl restart dnsmasq

infra: infra-push infra-restart

.PHONY: infra-push infra-restart infra

####################
# purpose is to tweak /etc/rhubarbe/rhubarbe.conf
# on preplab only
# to reflect the actual spare nodes
RC = /etc/rhubarbe/rhubarbe.conf.local
all-spares = $(shell cat r2lab-prep.spare-nodes)

spare-nodes: r2lab-prep.spare-nodes
	ssh root@preplab.pl.sophia.inria.fr \
          sed -i -e 's/all_scope.$(PREPLAB-HOSTNAME).*/all_scope.$(PREPLAB-HOSTNAME)=$(all-spares)/' $(RC)


####################
# preplab-configure and other similar targets
PREPLAB-TARGETS = configure rhubarbe infra

define preplab-target
preplab-$(1): GATEWAY=$(PREP_GATEWAY)
preplab-$(1): TBNAME=$(PREP_TBNAME)
preplab-$(1): $(1)

prep-$(1): preplab-$(1)

.PHONY: preplab-$(1) prep-$(1)
endef

$(foreach target,$(PREPLAB-TARGETS),$(eval $(call preplab-target,$(target))))

preplab: force $(foreach target,$(PREPLAB-TARGETS), preplab-$(target)) spare-nodes

force:

.PHONY: preplab
