# R2lab inventory : purpose

This subdir contains the tools to keep track of where each physical node sits
(a slot in the prod testbed on `faraday`, the preplab, or defunct),
and to generate the configuration of `dnsmasq` and `rhubarbe` from that.
The data is in `nodes.yaml`, and the tool is `inventory`.

* [AA-remap-nodes.md](AA-remap-nodes.md): how to move a node to another location
* [AA-setup-nodes.md](AA-setup-nodes.md): how to set up nodes, BIOS, known issues with CMC cards, etc..
* [AA-firewalld.md](AA-firewalld.md): glitches seen on the preplab with `dnsmasq` and `firewalld`
