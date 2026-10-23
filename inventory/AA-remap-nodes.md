# How to remap nodes in R2lab

When a node is broken, you want to replace it with another spare node.
This requires root access on faraday and preplab, and can be achieved as follows.

## Background

The tools in this directory configure the testbed deployed on `faraday.inria.fr` (and its sibling, the preplab), mostly in terms of both:

* `dnsmasq`, that serves DHCP and DNS to the nodes, and
* `rhubarbe`, that offers higher level tools for managing nodes status and images.

At some point it also targetted `nagios`, but this has gone unused over time.

Most of the time there is no discrepancy, i.e. node *X* sits on slot *X* in the chamber. However when a spare node needs to be deployed instead, the testbed needs to be reconfigured, and this is when you will need `r2lab-inventory`. It needs `click` and `pyyaml` (see `requirements.txt`), or just use `uv run r2lab-inventory ...`.

* Of course perform the physical replacement
* Then to apply changes, do the following from your own laptop (this is where you need to have rights to run `ssh root@faraday` and `ssh root@preplab`)

## Overview

```
cd r2lab-misc/inventory
git pull
# free the slot, then fill it
r2lab-inventory move 27 preplab
r2lab-inventory move 42 prod:27
r2lab-inventory set-note 27 "broken CMC"
r2lab-inventory list --prod
# just for extra safety
make clean
make remap
# do not forget to commit the change into the repo, e.g.
git add nodes.yaml
git commit -m "replaced node such-and-such with such-and-such"
git push
```

---

***IMPORTANT NOTE about propagation***  
the `make remap` stage pushes a new configuration towards the DNS server; be aware that these changes may take several minutes to propagate, so please be patient

---

## about `nodes.yaml`

The single source of truth is `nodes.yaml`. You should not need to edit this
file by hand; it contains one entry per physical node (the number on the label
glued to the node) like this:

```yaml
42:
  mac: "00:03:1d:0e:03:5b"
  wlan: ["7c:c3:a1:a8:26:9e", "7c:c3:a1:a8:1c:2a"]
  where: {prod: 27}      # or: prep | defunct
  note: "replaced fit27 2025-10"
```

The location of a node, `where`, is one of

* `{prod: N}` - deployed in faraday, at ceiling slot `N` (1..37)
* `prep` - in the preplab (a.k.a. v0)
* `defunct` - out of order

### the `list` command

`r2lab-inventory list [--prod|--prep|--defunct] [-v]` shows where the nodes are; it also warns about empty prod slots.

### the `move` command

`r2lab-inventory move PHY DESTINATION` where the destination is `prod:N`, `preplab` or `defunct`. The free-form note of a node is set with `r2lab-inventory set-note PHY NOTE` (an empty note removes it).

It fails if the destination slot is busy; so to replace the node in slot 27, first move it out of the way (to `preplab` or `defunct`), and then move the new one in. It also fails on a duplicate slot or MAC, and `list` / `generate` warn about empty prod slots.

### compute new config

```
parmentelat ~/git/r2lab-misc/inventory $ make configure
./r2lab-inventory -f nodes.yaml generate --prod
WARNING: empty prod slots: 04 06 13 15 17
(Over)wrote prod-inventory-nodes.yaml from nodes.yaml
<snip>...
```

The warning lists the prod slots that no node is deployed in.

### apply new config

for deploying this on faraday you can just run

 * `make publish`

    this would push everything needed onto faraday, and restart services if needed.

### preplab (preplab)

In the preplab, there is no notion of a physical location, of course. So a node labeled `fit23` or `fit42` will always we accessible as `fit23` or `fit42` resp., regardless of its location in `nodes.yaml`. So in this particular example no change is required on preplab.

Regardless, the following targets are available when targetting `preplab` instead:

* `make preplab` - to do it all
* `make preplab-configure`
* `make preplab-rhubarbe`
* `make preplab-infra`
