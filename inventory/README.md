# R2lab inventory : purpose

This subdir contains various tools for interacting with the testbed deployed on `faraday.inria.fr`, mostly in terms of both:
* `dnsmasq` that serves DHCP and DNS to the nodes, and
* `rhubarbe` that offers higher level tool for managing nodes status and images.

At some point it also targetted `nagios` but this has gone unused over time.

## Workflow

Mainly we manually maintain a local map in `r2lab.map`; this is where we map physical numbers (i.e. the ones on the label that is glued to the node) and logical numbers (the actual location in the room).

Most of the time of course there is no discrepency, i.e. node *X* sits on slot *X* in the chamber. However when a spare node needs to be deployed instead, the testbed needs to be reconfigured, and this is when you will need `inventory`.

## See also

In this directory:

* [AA-setup-nodes.md](AA-setup-nodes.md): how to set up nodes, BIOS, known issues with CMC cards, etc..
* [AA-remap-nodes.md](AA-remap-nodes.md): how to remap a node on another location

