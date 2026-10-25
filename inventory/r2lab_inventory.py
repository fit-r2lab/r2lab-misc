#!/usr/bin/env python3
# /// script
# requires-python = ">=3.8"
# dependencies = ["click", "pyyaml"]
# ///

# pylint: disable=missing-docstring, line-too-long, unspecified-encoding

"""
Manage the R2lab inventory: where each physical node (1..42) currently sits.

The single source of truth is nodes.yaml; it is rewritten by this tool
so that there is no need to edit it by hand.

Subcommands
  list      show where the nodes are
  move      move a physical node to prod:N, preplab or defunct
  set-note  set or remove the free-form note of a node
  generate  compute the config files (rhubarbe, dnsmasq, hosts, ...)
            for faraday and for the preplab; restrict with --prod or --prep
  publish   generate, then push the config files to faraday and/or the preplab
            and restart the services; --dry-run just shows the commands
  check-ssh run a command, by default `rhubarbe version`, on the gateways
            that publish talks to

Assumptions here:
(*) node with physical number 33 has its CM card burned with
    MAC address 02:00:00:00:00:33
(*) when eth0 has MAC address xx.xx.xx.xx.xx.81 then
    eth1 has MAC address xx.xx.xx.xx.xx.80
    this is probably too strong an assumption
    but is hopefully good enough for now
"""

import functools
import os
import re
import shlex
import subprocess
import sys
import textwrap
from pathlib import Path

import click
import yaml

DEFAULT_INVENTORY = Path(__file__).resolve().parent / "nodes.yaml"
PROD_SLOTS = range(1, 38)
PROD_PREFIX = "prod"
PREP_PREFIX = "prep"

PROD_GATEWAY = "root@faraday.inria.fr"
PREP_GATEWAY = "root@preplab.pl.sophia.inria.fr"

# where things go on the gateways
RHUBARBE_INVENTORY = "/etc/rhubarbe/inventory-nodes.yaml"
# xxx the one on faraday is assumed to be the same as on the preplab
RHUBARBE_CONF = "/etc/rhubarbe/rhubarbe.conf.local"
DNSMASQ_CONF = "/etc/NetworkManager/dnsmasq.d/03-testbed.conf"
HOSTS_CONF = "/etc/hosts"

# around the shell commands that a dry run displays
DELIMITER = 6 * "="

# where the slots are in the room, as seen on the livemap; None for the places
# that are not slots, like the two grey squares and the notch in the wall
ROOM_LAYOUT = (
    (1, 6, 11, 16, 19, 23, 26, 31, None),
    (2, 7, 12, None, 20, None, 27, 32, None),
    (3, 8, 13, 17, 21, 24, 28, 33, None),
    (4, 9, 14, 18, 22, 25, 29, 34, 36),
    (5, 10, 15, None, None, None, 30, 35, 37),
)
assert sorted(slot for row in ROOM_LAYOUT for slot in row if slot) == list(PROD_SLOTS)

MAC_REGEXP = re.compile(r'^([0-9a-f]{2}:){5}[0-9a-f]{2}$')

INVENTORY_HEADER = """\
# R2lab nodes inventory
#
# one entry per physical node, i.e. the number on the sticker glued to the node
# mac and wlan are hardware facts; 'where' is the only field that normally changes
#   where: {prod: N}   deployed in faraday at ceiling slot N (1..37)
#   where: prep        in the preplab (a.k.a. v0)
#   where: defunct     out of order
# use inventory to change it rather than editing this file by hand
"""


class InventoryError(Exception):
    pass


class Node:
    """
    a single node, defined with its physical number (given once and for good)
    and its current location, which is one of
    * ('prod', N)  - deployed in faraday at ceiling slot N
    * ('prep',)    - in the preplab
    * ('defunct',) - out of order
    in addition to a mac address (the one attached to its physical eth device)
    """

    def __init__(self, phy_num, mac, wlan, where, note=None):
        self.phy_num = phy_num
        self.mac = mac.lower()
        self.alt_mac = self._alt_mac(self.mac)
        self.wlan = [w.lower() for w in wlan]
        self.note = note
        self.relocate(where)

    def __repr__(self):
        return f"<Node phy={self.phy_num} where={self.where_str()}>"

    @staticmethod
    def _alt_mac(mac):
        "the mac of eth1 is the one of eth0 minus one"
        prefix, last = mac[:-2], int(mac[-2:], 16)
        return f"{prefix}{last - 1:02x}"

    # location
    @property
    def kind(self):
        return self.where[0]

    @property
    def slot(self):
        return self.where[1] if self.kind == 'prod' else None

    def relocate(self, where):
        self.where = where
        # the logical number is the slot in faraday; it is None otherwise
        self.log_num = self.slot

    def where_str(self):
        return f"prod:{self.slot:02d}" if self.kind == 'prod' else self.kind

    # (de)serialization
    @classmethod
    def from_yaml(cls, phy_num, entry):
        for key in ('mac', 'wlan', 'where'):
            if key not in entry:
                raise InventoryError(f"node {phy_num}: missing field '{key}'")
        mac = str(entry['mac']).lower()
        if not MAC_REGEXP.match(mac):
            raise InventoryError(f"node {phy_num}: wrong MAC '{mac}'")
        wlan = [str(w).lower() for w in entry['wlan']]
        if len(wlan) != 2 or not all(MAC_REGEXP.match(w) for w in wlan):
            raise InventoryError(f"node {phy_num}: wlan should be 2 valid MACs")
        return cls(phy_num, mac, wlan, cls._where_from_yaml(phy_num, entry['where']),
                   entry.get('note'))

    @staticmethod
    def _where_from_yaml(phy_num, where):
        if where in ('prep', 'defunct'):
            return (where,)
        if isinstance(where, dict) and list(where) == ['prod']:
            slot = where['prod']
            if isinstance(slot, int) and slot in PROD_SLOTS:
                return ('prod', slot)
            raise InventoryError(
                f"node {phy_num}: prod slot should be in {PROD_SLOTS.start}"
                f"..{PROD_SLOTS.stop - 1}, not {slot!r}")
        raise InventoryError(
            f"node {phy_num}: wrong location {where!r} - "
            f"expecting {{prod: N}}, prep or defunct")

    def to_yaml(self):
        if self.kind == 'prod':
            where = f"{{prod: {self.slot}}}"
        else:
            where = self.kind
        lines = [f'{self.phy_num}:',
                 f'  mac: "{self.mac}"',
                 f'  wlan: ["{self.wlan[0]}", "{self.wlan[1]}"]',
                 f'  where: {where}']
        if self.note:
            note = yaml.safe_dump(str(self.note), default_style='"', width=10**6).splitlines()[0]
            lines.append(f'  note: {note}')
        return "\n".join(lines) + "\n"

    # names and addresses
    def phy_str0(self):
        "physical number on 2 chars as a str"
        return f"{self.phy_num:02d}"

    def log_str0(self):
        "logical number on 2 chars as a str"
        return f"{self.log_num:02d}"

    def log_name(self, prefix='fit'):
        "external name based on logical number, like fit33"
        return f"{prefix}{self.log_num:02d}"

    subnets = ((1, 'reboot'), (2, 'data'), (3, 'control'))

    def rhubarbe_model(self):
        return {
            'cmc': {
                'hostname': self.log_name(prefix='reboot'),
                'mac': f"02:00:00:00:00:{self.phy_str0()}",
                'ip':  f"192.168.1.{self.phy_num}",
                },
            'control': {
                'hostname': self.log_name(),
                'mac': self.mac,
                'ip':  f"192.168.3.{self.log_num}",
                },
            'data': {
                'hostname': self.log_name(prefix="data"),
                'mac': self.alt_mac,
                'ip':  f"192.168.2.{self.log_num}",
                }
            }

    def dnsmasq_conf(self):
        # for the control interfaces, provide IP + hostname
        control = (f"dhcp-host=net:control,"
                   f"{self.mac},192.168.3.{self.log_num},"
                   f"{self.log_name('fit')}")
        # do not expose a hostname on the data subnet
        data = (f"dhcp-host=net:data,"
                f"{self.alt_mac},192.168.2.{self.log_num}")
        return "".join(x+"\n" for x in (control, data))

    def hosts_conf_sn(self, sn_ip, sn_name):
        # we cannot change the IP address of the CMC card,
        # so this one is physical
        is_cmc = sn_ip == self.subnets[0][0]
        num = self.phy_num if is_cmc else self.log_num
        hostnames = self.log_name(prefix=sn_name)
        if sn_name == 'control':
            hostnames = self.log_name() + " " + hostnames
        return f"192.168.{sn_ip}.{num}\t{hostnames}\n"

    def hosts_conf(self):
        return "".join([self.hosts_conf_sn(i, n) for (i, n) in self.subnets])


def dummy_hosts_conf(phy_num):
    """
    missing nodes like reboot04 still get defined in /etc/hosts
    in order to optimize the DNS traffic to the outside world
    """
    return f"192.168.4.{phy_num}\treboot{phy_num:02d}\n"


########################################
HOSTS_HEADER = """# Do not edit this file directly
# it is generated by r2lab-inventory

127.0.0.1	localhost

# The following lines are desirable for IPv6 capable hosts
::1     localhost ip6-localhost ip6-loopback
ff02::1 ip6-allnodes
ff02::2 ip6-allrouters

# the interfaces in the gateway on the various networks
192.168.1.100   rhubarbe-reboot faraday1
192.168.2.100   rhubarbe-data faraday2
192.168.3.100   rhubarbe-control faraday3
192.168.4.100   rhubarbe-switches faraday4
# actual switches on the production deployment
192.168.4.101   switch-reboot
192.168.4.102   switch-data
192.168.4.103   switch-control
192.168.4.104   switch-c007
192.168.4.105   switch-radio
192.168.4.36    wlab36
# this is for the apple thunderbolt/ethernet adapter in the room
192.168.4.150   mac-thunder
# self-service IP's on VLAN 40
192.168.4.151   insider1 insider
192.168.4.152   insider2
# the mac units that are permanently present in the chamber
192.168.4.201   macphone1 macphone
192.168.4.202   macphone2
192.168.4.203   macphone3
192.168.4.204   macphone4
###
# actual switch on the preplab - a.k.a. v0
192.168.3.200   switch07
#
# access to the control network from slices-ri
192.168.3.210   sopnode-gw1
192.168.3.211   sopnode-gw2
#
# access to the control network from sopnode-l1/sopnode-w1
192.168.3.250   sopnode-l1
192.168.3.251   sopnode-w1
#
###
# the blackbox remote-power device (admin/adminet++)
# it DOES NOT support DHCP and requires to be configured manually
# for the record, its MAC address is 00.01.9A.F1.10.F6
# it allows to power-cycle:
#   * 1: N310
#   * 2: X310
#   * 3: Macphone 1
#   * 4: Sw4
#
# its X310 companion
192.168.3.151   n300-1 n300
192.168.3.152   n320-1 n320
192.168.4.106   pdu1
192.168.4.107   pdu2
# actually in C007 - optimize the DNS traffic to the outside world
138.96.245.30   sopnode-pdu-bas.inria.fr sopnode-pdu-basq
138.96.245.31   sopnode-pdu-haut.inria.fr sopnode-pdu-haut
###
# set of relays boxes based on Raspberry Pi 3B devices
# used to control qhat/pc/benetel devices.
# Each relay box is composed of a raspberry Pi relay-XX and a switch sw-relay-XX
192.168.1.101   relay-01
192.168.1.102   relay-02
192.168.1.103   relay-03
192.168.1.104   relay-04
192.168.1.105   relay-05
192.168.1.106   relay-06
192.168.1.107   relay-07
192.168.1.108   relay-08
192.168.1.109   relay-09
192.168.1.110   relay-10
#
192.168.1.141   sw-relay-01
192.168.1.142   sw-relay-02
192.168.1.143   sw-relay-03
192.168.1.144   sw-relay-04
192.168.1.145   sw-relay-05
192.168.1.146   sw-relay-06
192.168.1.147   sw-relay-07
192.168.1.148   sw-relay-08
192.168.1.149   sw-relay-09
192.168.1.150   sw-relay-10
#
###
# set of Raspberry Pi 4B qhat devices with 5G Quectel RM 500Q-GL modules
192.168.3.51    qhat01
192.168.3.52    qhat02
192.168.3.53    qhat03
# set of Raspberry Pi 4B qhat devices with 5G Quectel RM520N-GL modules
192.168.3.60 	qhat10
192.168.3.61 	qhat11
# set of Raspberry Pi 4B qhat devices with 5G Quectel RG255C-GL modules
192.168.3.70 	qhat20
192.168.3.71 	qhat21
192.168.3.72 	qhat22
192.168.3.73 	qhat23
# set of qfit UEs (5G Quectel RM 500Q-GL modules connected to some FIT nodes, correspond to the control interface of those)
192.168.3.7     qfit07
192.168.3.9     qfit09
192.168.3.18    qfit18
192.168.3.29    qfit29
192.168.3.32    qfit32
192.168.3.34    qfit34
###
# Two miniPC UM690 devices with USRP B210 module attached
192.168.3.91    pc01
192.168.3.92    pc02
#
# Two miniPC UP4000 devices with UE Quectel RG530F attached
192.168.3.93    pc03
192.168.3.94    pc04
###
# following reserved for 5G k8s scenarios between R2lab and sopnode-w1/sopnode-l1
192.168.3.201   pod1
192.168.3.202   pod2
192.168.3.203   pod3
192.168.3.204   pod4
192.168.3.205   pod5
192.168.3.206   pod6
192.168.3.207   pod7
192.168.3.208   pod8
#
##########
"""

DNSMASQ_HEADER = """# Do not edit this file directly
# it is generated by r2lab-inventory

### SWITCHES
# the network switches are now configured statically
# for the record we keep their MAC addresses
#
# CONFIRMED to be the main data switch
#dhcp-host=f8:b1:56:33:50:ad,switch-data,192.168.4.102
# CONFIRMED control
#dhcp-host=f8:b1:56:42:51:32,switch-control,192.168.4.103
# CONFIRMED reboot
#dhcp-host=f8:b1:56:42:52:a5,switch-reboot,192.168.4.101
# switch in C007 type 5524
#dhcp-host=d0:67:e5:d6:ae:fe,switch-c007,192.168.4.104
# switch radio (fs.com) in R2lab - uses DHCP for now
dhcp-host=64:9D:99:D0:57:52,switch-radio,192.168.4.105
# PDU #1 - sur prise reboot #40
dhcp-host=00:20:85:DC:DE:45,pdu1,192.168.4.106
# PDU #2 - sur prise reboot #38
dhcp-host=00:20:85:DC:DC:79,pdu2,192.168.4.107

### APPLE mac minis
# macphone1 used to be a macbook air pinaragnata - or something along this line
#dhcp-host=d8:30:62:a5:3b:a7,macphone1,192.168.4.201
# replaced in nov 2018 with a mac mini simply named macphone1
dhcp-host=14:c2:13:ec:b4:b9,macphone1,192.168.4.201
# macphone2 is a mac mini
# it has a USB link to a motorola moto E 4G
dhcp-host=a8:60:b6:24:f9:4d,macphone2,192.168.4.202
# the apple ethernet-to-thunderbolt adapter in the room
dhcp-host=6c:40:08:b6:c1:7e,mac-thunder,192.168.4.150

# N300 - N320
dhcp-host=00:80:2F:30:9A:8A,n300-1,192.168.3.151
dhcp-host=00:80:2F:28:3C:28,n320-1,192.168.3.152

### DHCP config for relays boxes 
# Currently 10 new relays added based on raspberryPi 3B.
# They control various devices in R2lab. Each one
# is included in a box with a switch-relay.
# IP addresses are in the reboot network.
# These relays are now configured statically
# for the record we keep their MAC addresses
#dhcp-host=b8:27:eb:f9:65:2e,relay-01,192.168.1.101
#dhcp-host=b8:27:eb:24:a6:d6,relay-02,192.168.1.102
#dhcp-host=b8:27:eb:31:9c:a0,relay-03,192.168.1.103
#dhcp-host=b8:27:eb:cd:c7:1e,relay-04,192.168.1.104
#dhcp-host=b8:27:eb:91:f7:0b,relay-05,192.168.1.105
#dhcp-host=b8:27:eb:d6:c9:eb,relay-06,192.168.1.106
#dhcp-host=b8:27:eb:ce:69:53,relay-07,192.168.1.107
#dhcp-host=b8:27:eb:fc:32:88,relay-08,192.168.1.108
#dhcp-host=b8:27:eb:13:11:02,relay-09,192.168.1.109
#dhcp-host=b8:27:eb:5d:18:20,relay-10,192.168.1.110
#
### RELAY-SWITCHES
# Relay-switches (in the same boxes than new relays)
# These relays use DHCP to configure their management addresses
dhcp-host=54:07:7D:20:C0:6D,sw-relay-01,192.168.1.141
dhcp-host=54:07:7D:20:CD:40,sw-relay-02,192.168.1.142
dhcp-host=54:07:7D:20:C2:65,sw-relay-03,192.168.1.143
dhcp-host=54:07:7D:20:C2:5F,sw-relay-04,192.168.1.144
dhcp-host=54:07:7D:20:B5:F1,sw-relay-05,192.168.1.145
dhcp-host=54:07:7D:20:C1:8F,sw-relay-06,192.168.1.146
dhcp-host=54:07:7D:20:BA:E5,sw-relay-07,192.168.1.147
dhcp-host=54:07:7D:20:BC:90,sw-relay-08,192.168.1.148
dhcp-host=54:07:7D:20:C0:6B,sw-relay-09,192.168.1.149
dhcp-host=54:07:7D:20:BD:49,sw-relay-10,192.168.1.150

######### preplab
# the 1Gbps switch attached to distrait in preplab
dhcp-host=00:27:0c:ff:cc:48,switch07,192.168.3.200


"""


class Inventory(dict):
    """
    a repository of known nodes, indexed by physical number
    """
    def __init__(self, filename):
        super().__init__()
        self.filename = Path(filename)

    def load(self):
        try:
            with open(self.filename) as feed:
                data = yaml.safe_load(feed)
        except FileNotFoundError as exc:
            raise InventoryError(f"cannot open {self.filename}") from exc
        except yaml.YAMLError as exc:
            raise InventoryError(f"{self.filename}: {exc}") from exc
        if not isinstance(data, dict):
            raise InventoryError(f"{self.filename}: expecting a mapping phy -> node")
        for phy_num, entry in sorted(data.items()):
            if not isinstance(phy_num, int) or phy_num <= 0:
                raise InventoryError(f"{self.filename}: wrong physical number {phy_num!r}")
            self[phy_num] = Node.from_yaml(phy_num, entry)
        self.validate()
        return self

    def validate(self):
        "hard errors: the same mac or the same slot used twice"
        macs, slots = {}, {}
        for node in self.values():
            for mac in (node.mac, node.alt_mac):
                if mac in macs:
                    raise InventoryError(
                        f"MAC {mac} used by both nodes {macs[mac]} and {node.phy_num}")
                macs[mac] = node.phy_num
            if node.kind == 'prod':
                if node.slot in slots:
                    raise InventoryError(
                        f"prod slot {node.slot} used by both nodes "
                        f"{slots[node.slot]} and {node.phy_num}")
                slots[node.slot] = node.phy_num

    def save(self):
        text = INVENTORY_HEADER + "".join(
            "\n" + node.to_yaml() for _, node in sorted(self.items()))
        tmp = self.filename.with_suffix(".yaml.tmp")
        tmp.write_text(text)
        tmp.replace(self.filename)

    def spare_nodes(self):
        "the physical numbers of the nodes in the preplab, like 04,11,14"
        return ",".join(n.phy_str0() for _, n in sorted(self.items())
                        if n.kind == 'prep')

    def prod_scope(self):
        "the scope of rhubarbe -a in faraday, like 1-37,~4,~6"
        return f"{PROD_SLOTS.start}-{PROD_SLOTS.stop - 1}" + "".join(
            f",~{slot}" for slot in self.empty_slots())

    def room_layout(self):
        """
        the nodes in prod as a drawing of the room; each cell is the slot,
        then the physical number of the node in that slot, or -- if there
        is no node there; in light red when the node is not the one that
        has the same number as the slot, and in light blue for an empty slot
        """
        by_slot = {node.slot: node for node in self.in_prod()}

        def cell(slot):
            if slot is None:
                return " " * 5
            node = by_slot.get(slot)
            text = f"{slot:02d}:" + (f"{node.phy_num:02d}" if node else "--")
            if node is None:
                return click.style(text, fg="bright_blue")
            if node.phy_num != slot:
                return click.style(text, fg="bright_red")
            return text

        return "\n".join(("  ".join(cell(slot) for slot in row)).rstrip()
                         for row in ROOM_LAYOUT)

    def in_prod(self):
        return sorted((n for n in self.values() if n.kind == 'prod'),
                      key=lambda n: n.slot)

    def empty_slots(self):
        taken = {n.slot for n in self.in_prod()}
        return [s for s in PROD_SLOTS if s not in taken]

    def warn_empty_slots(self):
        empty = self.empty_slots()
        if empty:
            print("WARNING: empty prod slots: "
                  + " ".join(f"{s:02d}" for s in empty), file=sys.stderr)

    # generating the configuration files
    def exposed(self, prep_lab):
        """
        returns (nodes, missing) where nodes are those that get exposed
        and missing the physical numbers that only get a placeholder
        in regular mode, we expose the nodes that are deployed in faraday
        in prep_lab mode we expose all nodes under their physical number
        """
        if prep_lab:
            for node in self.values():
                node.log_num = node.phy_num
            return list(self.values()), []
        return (list(self.in_prod()),
                [n.phy_num for n in self.values() if n.kind != 'prod'])

    def generate(self, prep_lab, prefix):
        try:
            self._generate(prep_lab, prefix)
        finally:
            # exposing in prep mode alters the logical numbers
            for node in self.values():
                node.log_num = node.slot

    def _generate(self, prep_lab, prefix):
        nodes, missing = self.exposed(prep_lab)
        # regular mode is in the order of physical numbers, like before
        if not prep_lab:
            nodes.sort(key=lambda n: n.phy_num)

        def write(out_filename, text):
            with open(out_filename, 'w') as outfile:
                outfile.write(text)
            # fixed width, so the names line up; 25 fits prep-inventory-nodes.yaml
            print(f"(Over)wrote {out_filename:<25} from {os.path.relpath(self.filename)}")

        models = [node.rhubarbe_model() for node in nodes]
        write(f"{prefix}-inventory-nodes.yaml", yaml.safe_dump({'nodes': models}, sort_keys=True))
        write(f"{prefix}-dnsmasq", DNSMASQ_HEADER + "\n" + 20*'#' + "\n"
              + "".join(node.dnsmasq_conf() for node in nodes))
        write(f"{prefix}-hosts", HOSTS_HEADER
              + "".join(node.hosts_conf() for node in nodes)
              + "".join(dummy_hosts_conf(phy) for phy in missing))


########################################
def parse_destination(text):
    "prod:12 | preplab | prep | defunct -> a Node.where tuple"
    if text in ('prep', 'preplab'):
        return ('prep',)
    if text == 'defunct':
        return ('defunct',)
    match = re.match(r'^prod:(\d+)$', text)
    if match and int(match.group(1)) in PROD_SLOTS:
        return ('prod', int(match.group(1)))
    raise InventoryError(
        f"wrong destination '{text}' - expecting prod:N with N in "
        f"{PROD_SLOTS.start}..{PROD_SLOTS.stop - 1}, preplab or defunct")


def shell_join(argv):
    "like shlex.join, but prefers double quotes over escaping single quotes"
    def quote(arg):
        if "'" in arg and not any(char in arg for char in '"$`\\!'):
            return f'"{arg}"'
        return shlex.quote(arg)
    return " ".join(quote(arg) for arg in argv)


def publish_commands(inventory, prep_lab):
    """
    the commands, as argv lists, that push the files computed by generate
    to the gateway of faraday, or of the preplab
    """
    prefix, gateway, scope = (
        (PREP_PREFIX, PREP_GATEWAY, inventory.spare_nodes()) if prep_lab else
        (PROD_PREFIX, PROD_GATEWAY, inventory.prod_scope()))
    # reflect the actual nodes in the scope of rhubarbe -a
    # this also converts the older all_scope.<hostname> form
    sed = f"s/^all_scope[.=].*/all_scope={scope}/"
    return [
        ["rsync", "-vrltp", f"{prefix}-inventory-nodes.yaml", f"{gateway}:{RHUBARBE_INVENTORY}"],
        ["rsync", "-rltp", f"{prefix}-dnsmasq", f"{gateway}:{DNSMASQ_CONF}"],
        ["rsync", "-rltp", f"{prefix}-hosts", f"{gateway}:{HOSTS_CONF}"],
        # restarting also cleans up the leases file; otherwise the new node
        # may need to wait for some time before it gets served its address
        # and could get stuff like 192.168.3.251 instead
        ["ssh", gateway, "systemctl restart NetworkManager"],
        ["ssh", gateway, f"sed -i -e '{sed}' {RHUBARBE_CONF}"],
    ]


def get_node(inventory, phy):
    node = inventory.get(phy)
    if node is None:
        raise InventoryError(f"no such physical node {phy}")
    return node


class OrderedGroup(click.Group):
    "list the subcommands in --help in this order, not alphabetically"
    ORDER = ("list", "move", "set-note", "generate", "check-ssh", "publish")

    def list_commands(self, ctx):
        known = [name for name in self.ORDER if name in self.commands]
        return known + sorted(set(self.commands) - set(known))

    # also accept any unambiguous prefix of a subcommand, like 'ge' for generate
    def get_command(self, ctx, cmd_name):
        command = super().get_command(ctx, cmd_name)
        if command is not None:
            return command
        matches = [name for name in self.list_commands(ctx)
                   if name.startswith(cmd_name)]
        if len(matches) > 1:
            ctx.fail(f"'{cmd_name}' is ambiguous: could be {', '.join(matches)}")
        return super().get_command(ctx, matches[0]) if matches else None

    def resolve_command(self, ctx, args):
        # use the actual name rather than the abbreviation
        name, command, rest = super().resolve_command(ctx, args)
        return (command.name if command else name), command, rest


@click.group(cls=OrderedGroup, context_settings={'help_option_names': ['-h', '--help']})
@click.option("-f", "--file", "filename", default=DEFAULT_INVENTORY,
              show_default=True, help="inventory file")
@click.pass_context
def main(ctx, filename):
    """Manage the R2lab inventory: where each physical node currently sits."""
    try:
        ctx.obj = Inventory(filename).load()
    except InventoryError as exc:
        raise click.ClickException(str(exc)) from exc


def run(func):
    "turn our own errors into regular click errors"
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except InventoryError as exc:
            raise click.ClickException(str(exc)) from exc
        except subprocess.CalledProcessError as exc:
            raise click.ClickException(f"failed: {shell_join(exc.cmd)}") from exc
    return wrapper


@main.command(name="help", hidden=True)
@click.pass_context
def help_(ctx):
    "same as --help"
    click.echo(ctx.parent.get_help())


@main.command(name="list")
@click.option("--prod", is_flag=True, help="only nodes in prod")
@click.option("--prep", is_flag=True, help="only nodes in the preplab")
@click.option("--defunct", is_flag=True, help="only defunct nodes")
@click.option("-v", "--verbose", is_flag=True,
              help="one line per node, with note")
@click.pass_obj
@run
def list_(inventory, prod, prep, defunct, verbose):
    """Show where the nodes are.

    By default, a drawing of the room: each cell is the ceiling slot, then
    the physical number of the node there, or -- for an empty slot;
    followed by the nodes in the preplab and the defunct ones.
    """
    kinds = [kind for kind, wanted in
             (('prod', prod), ('prep', prep), ('defunct', defunct)) if wanted]
    kinds = kinds or ['prod', 'prep', 'defunct']
    if verbose:
        nodes = inventory.in_prod() if kinds == ['prod'] else inventory.values()
        for node in nodes:
            if node.kind in kinds:
                where = f"{node.where_str():<7}"
                # same red as in the room layout for a node not in its own slot
                if node.kind == 'prod' and node.phy_num != node.slot:
                    where = click.style(where, fg="bright_red")
                elif node.kind != 'prod':
                    where = click.style(where, fg="bright_blue")
                line = f"{node.phy_num:02d}  {where}"
                click.echo(line + (f"  # {node.note}" if node.note else ""))
        return
    if 'prod' in kinds:
        # click.echo drops the colors when not writing to a terminal
        click.echo("prod")
        click.echo(textwrap.indent(inventory.room_layout(), "  "))
    for kind in ('prep', 'defunct'):
        if kind in kinds:
            phys = " ".join(f"{n.phy_num:02d}" for n in inventory.values()
                            if n.kind == kind)
            print(f"{kind}: {phys or '-'}")


@main.command()
@click.argument("phy", type=int)
@click.argument("destination")
@click.pass_obj
@run
def move(inventory, phy, destination):
    """Move a physical node; DESTINATION is prod:N, preplab or defunct.

    Fails if the destination slot is busy, so to replace the node in a slot,
    first move that one away.
    """
    node = get_node(inventory, phy)
    where = parse_destination(destination)
    if where == node.where:
        raise InventoryError(f"node {node.phy_num} is already at {node.where_str()}")
    if where[0] == 'prod':
        for other in inventory.values():
            if other.where == where:
                raise InventoryError(
                    f"prod slot {where[1]} is busy with node {other.phy_num} "
                    f"- move it away first, e.g. inventory move {other.phy_num} preplab")
    previous = node.where_str()
    node.relocate(where)
    inventory.validate()
    inventory.save()
    print(f"node {node.phy_num:02d}: {previous} -> {node.where_str()}")
    if previous.startswith('prod'):
        print(f"slot {previous[5:]} is now free")


@main.command(name="set-note")
@click.argument("phy", type=int)
@click.argument("note")
@click.pass_obj
@run
def set_note(inventory, phy, note):
    """Set the free-form note of a node; an empty NOTE removes it."""
    node = get_node(inventory, phy)
    node.note = note or None
    inventory.save()
    print(f"node {node.phy_num:02d}: " + (f"note is '{note}'" if note else "note removed"))


@main.command()
@click.option("--prod", is_flag=True, help="only for faraday")
@click.option("--prep", is_flag=True,
              help="only for the preplab, where all nodes are exposed under their physical number")
@click.pass_obj
@run
def generate(inventory, prod, prep):
    """Compute the config files; for both prod and prep unless restricted."""
    both = not (prod or prep)
    if prod or both:
        inventory.warn_empty_slots()
        inventory.generate(False, PROD_PREFIX)
    if prep or both:
        inventory.generate(True, PREP_PREFIX)


@main.command()
@click.option("--prod", is_flag=True, help="only for faraday")
@click.option("--prep", is_flag=True, help="only for the preplab")
@click.option("-n", "--dry-run", is_flag=True,
              help="do not push anything, just show the commands, ready to cut and paste")
@click.pass_obj
@run
def publish(inventory, prod, prep, dry_run):
    """Generate the config files, push them, and restart the services.

    For both prod and prep unless restricted. The config files are always
    computed locally; with --dry-run that is all that happens, and the
    commands that would push them are shown instead of being run.
    """
    both = not (prod or prep)
    for prep_lab in (False, True):
        if not (prep if prep_lab else prod) and not both:
            continue
        name = "prep" if prep_lab else "prod"
        if not prep_lab:
            inventory.warn_empty_slots()
        inventory.generate(prep_lab, PREP_PREFIX if prep_lab else PROD_PREFIX)
        print(f"# {name}{' (dry run)' if dry_run else ''}")
        if dry_run:
            print(DELIMITER)
        for argv in publish_commands(inventory, prep_lab):
            if dry_run:
                print(shell_join(argv))
            else:
                print(f"$ {shell_join(argv)}", flush=True)
                subprocess.run(argv, check=True)
        if dry_run:
            print(DELIMITER)


@main.command(name="check-ssh", context_settings={'ignore_unknown_options': True})
@click.option("--prod", is_flag=True, help="only faraday")
@click.option("--prep", is_flag=True, help="only the preplab")
@click.option("-n", "--dry-run", is_flag=True, help="just show the commands")
@click.argument("command", nargs=-1, type=click.UNPROCESSED)
@click.pass_obj
@run
def check_ssh(inventory, prod, prep, dry_run, command):
    """Run COMMAND on the gateways that publish talks to.

    By default this is rhubarbe version; so it can be used to check
    that ssh access works, before publishing. Options come first.
    """
    del inventory
    remote = " ".join(command) or "rhubarbe version"
    both = not (prod or prep)
    failures = []
    for gateway, wanted in ((PROD_GATEWAY, prod), (PREP_GATEWAY, prep)):
        if not (wanted or both):
            continue
        argv = ["ssh", gateway, remote]
        if dry_run:
            print(shell_join(argv))
            continue
        print(f"$ {shell_join(argv)}", flush=True)
        if subprocess.run(argv, check=False).returncode != 0:
            failures.append(gateway)
    if failures:
        raise InventoryError("failed on " + " and ".join(failures))


if __name__ == '__main__':
    main()
