#!/usr/bin/env python3

# pylint: disable=f-string-without-interpolation, bare-except
# pylint: disable=missing-docstring, line-too-long, unspecified-encoding

"""
Assumptions here:
(*) node with physical number 33 has its CM card burned with
    MAC address 02:00:00:00:00:33
(*) when eth0 has MAC address xx.xx.xx.xx.xx.81 then
    eth1 has MAC address xx.xx.xx.xx.xx.80
    this is probably too strong an assumption
    but is hopefully good enough for now
"""

import re
import json
# as of June 2015, we don't use a csv file as input but r2lab.map instead
# import csv

from argparse import ArgumentParser

from collections import OrderedDict

########################################
mac_regexp = re.compile(
    '(?P<prefix>([0-9A-Fa-f]{2}:){5})(?P<last>[0-9A-Fa-f]{2})')


class Node:
    """
    a single node, defined with its physycal number (given once and for good)
    a logical number (the actual slot in the testbed where this node sits)
    and a mac addredd (the one attached to its physical eth device)
    ---
    """
    def __init__(self, phy_num, log_num, mac, alt_mac, spare):
        self.phy_num = phy_num
        self.log_num = log_num
        self.mac = mac.lower()
        self.alt_mac = alt_mac.lower()
        self.spare = spare

    def __repr__(self):
        return (f"<Node phy={self.phy_num}, log={self.log_num}"
                f" - spare={self.spare}>")

    def phy_str0(self):
        "physical number on 2 chars as a str"
        return f"{self.phy_num:02d}"

    def phy_name(self):
        "external name based on physical number, like phy33"
        return f"phy{self.phy_str0()}"

    def log_str0(self):
        "logical number on 2 chars as a str"
        return f"{self.log_num:02d}"

    def log_name(self, prefix='fit'):
        "external name based on logical number, like fit33"
        return f"{prefix}{self.log_num:02d}"

    subnets = ((1, 'reboot'), (2, 'data'), (3, 'control'))

    @staticmethod
    def degree_to_float(tuple_):
        deg, min_, sec = tuple_
        return deg + min_/60 + sec/3600

    # all nodes get the same position for now
    def longitude(self):
        return self.degree_to_float((7, 4, 9.30))

    def latitude(self):
        return self.degree_to_float((43, 36, 52.30))

    # def omf_json_model(self):
    #     domain = 'r2lab'
    #     return OrderedDict(
    #         cmc_attributes={
    #             "name": f"{self.log_name()}:cm",
    #             "mac": f"02:00:00:00:00:{self.phy_str0()}",
    #             "ip_attributes": {
    #                 # we cannot change the IP address of the CMC ...
    #                 "address": f"192.168.1.self.phy_num",
    #                 "netmask": "255.255.255.0",
    #                 "ip_type": "ipv4"
    #             }
    #         },
    #         cpus_attributes=[
    #             {
    #                 "cpu_type": "Intel 4770kI7",
    #                 "cores": 4,
    #                 "threads": 8,
    #                 "cache_l1": "n/a",
    #                 "cache_l2": "8 Mb",
    #             }
    #         ],
    #         domain=domain,
    #         gateway='faraday.inria.fr',
    #         hardware_type="PC-Icarus",
    #         hd_capacity="240 GB",
    #         hostname=self.phy_name(),
    #         interfaces_attributes=[
    #             {
    #                 "role": "control",
    #                 "name": f"{self.log_name()}:if0",
    #                 "mac": self.mac,
    #                 "ips_attributes": [{
    #                     f"address": "192.168.3.{self.log_num}",
    #                     "netmask": "255.255.255.0",
    #                     "ip_type": "ipv4"
    #                 }],
    #             },
    #             {
    #                 "role": "experimental",
    #                 "name": f"{self.log_name()}:if1",
    #                 "mac": self.alt_mac
    #             },
    #         ],
    #         # todo: needs to be made much more accurate
    #         location_attributes={
    #             'altitude': 145,
    #             'latitude': self.latitude(),
    #             'longitude': self.longitude(),
    #             },
    #         name=self.log_name(),
    #         ram="8 GB",
    #         ram_type="DIMM Synchronous",
    #         urn=f"urn:publicid:IDN+r2lab+node+{self.log_name()}",
    #     )

    # # I'd like to keep the previous code intact for now
    # def hacked_omf_json_model(self):
    #     json_ = self.omf_json_model()
    #     # patch
    #     json_['name'] = '37nodes'
    #     json_['urn'] = json_['urn'].replace(self.log_name(), json_['name'])
    #     # cleanup
    #     del json_['cmc_attributes']
    #     del json_['hostname']
    #     del json_['interfaces_attributes']
    #     return json_

    def rhubarbe_json_model(self):
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

    def diana_db(self):
        ip_ = f"138.96.119.{100+self.phy_num}"
        hostname = self.phy_name()
        mac1 = self.mac
        mac2 = self.alt_mac
        return f"{ip_} h={hostname} {mac1} o=alt:{mac2}\n"


class DummyNode(Node):
    """
    missing nodes like reboot04 still get defined in /etc/hosts
    in order to optimize the DNS traffic to the outside world
    """

    def __init__(self, phy_num) -> None:
        self.phy_num = phy_num

    def reboot_name(self):
        return f"reboot{self.phy_str0()}"

    def dummy_hosts_conf(self):
        return f"192.168.4.{self.phy_num}\t{self.reboot_name()}\n"


########################################
HOSTS_HEADER = """# Do not edit this file directly
# it is generated by configure.py

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
# actual switch on the preplab - a.k.a. etourdi/v0
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
# it is generated by configure.py

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
# the 1Gbps switch attached to etourdi in preplab
dhcp-host=00:27:0c:ff:cc:48,switch07,192.168.3.200


"""


class Nodes(OrderedDict):
    """
    a repository of known nodes, indexed by physical number
    """
    def __init__(self, map_filename, out_basename, prep_lab, verbose):
        OrderedDict.__init__(self)
        self.map_filename = map_filename
        self.out_basename = out_basename
        self.prep_lab = prep_lab
        self.verbose = verbose
        self._missing = set()

    # format of a .map file is straightforward
    # (1) first column is the pysical number written on the box (sticker)
    # (2) second column is its main mac address
    # (3) last column is its logical location where it is deployed in faraday
    #
    # in regular mode, we hide nodes that are declared in preplab
    # in prep_lab mode we expose all nodes, ignore column 3
    # and use column 1 instead
    def load(self):
        filename = self.map_filename
        with open(filename, 'r') as mapfile:
            for lno, line in enumerate(mapfile, 1):
                # ignore comments
                if line.startswith('#'):
                    continue
                tokens = line.split()
                if len(tokens) != 5:
                    print(f"{filename}:{lno}: expecting 5 tokens - ignored")
                    continue
                # get node number
                try:
                    phy_num = int(tokens[0])
                except:
                    print(f"{filename}:{lno}: cannot read first integer")
                    continue
                # get logical number
                spare = False
                if tokens[2] in ('preplab', 'greece'):
                    log_num = 0
                    spare = True
                else:
                    try:
                        log_num = int(tokens[2])
                    except:
                        print(f"{filename}:{lno}: cannot read last integer")
                        continue
                if self.prep_lab:
                    log_num = phy_num
                # discard nodes that are not on-site
                if log_num <= 0:
                    print(f"{filename}:{lno} - undeployed physical node {phy_num} - will be padded")
                    self._missing.add(phy_num)
                    continue
                mac = tokens[1]
                match = mac_regexp.match(mac)
                if match:
                    prefix, last = match.group('prefix', 'last')
                    byte = int(last, base=16)
                    alt_last = hex(byte-1)[2:]
                    alt_mac = prefix+alt_last
                    self[phy_num] = Node(phy_num, log_num, mac, alt_mac, spare)
                else:
                    print(f"{filename}:{lno} physical node {phy_num} ignored - wrong MAC")
                    if self.verbose:
                        print(">>", line)

    def keep_just_one(self):
        for k in self.keys()[1:]:
            del self[k]
        self.out_basename += ".small"

    def write_json(self):
        # out_filename = self.out_basename+"-omf.json"
        # with open(out_filename, 'w') as jsonfile:
        # # nov. 2015 : expose only one node to onelab / sfa
        # #    json_models = [ node.omf_json_model() for node in self.values() ]
        #     first_node = list(self.values())[0]
        #     one_json_model = first_node.hacked_omf_json_model()
        #     json.dump([one_json_model], jsonfile, indent=2,
        #               separators=(',', ': '), sort_keys=True)
        # print(f"(Over)wrote {out_filename} from {self.map_filename}")
        out_filename = self.out_basename+".rhubarbe.json"
        with open(out_filename, 'w') as jsonfile:
            json_models = [node.rhubarbe_json_model() for node in self.values()]
            json.dump(json_models, jsonfile, indent=2, separators=(',', ': '), sort_keys=True)
        print(f"(Over)wrote {out_filename} from {self.map_filename}")

    def write_all_prep_nodes(self):
        out_filename = self.out_basename+".spare-nodes"
        with open(out_filename, 'w') as spare_nodes:
            indices = ",".join([node.phy_str0() for node in self.values() if node.spare])
            spare_nodes = spare_nodes.write(indices + "\n")
        print(f"(Over)wrote {out_filename} from {self.map_filename}")

    def write_dnsmasq(self):
        out_filename = self.out_basename+".dnsmasq"
        with open(out_filename, 'w') as dnsmasqfile:
            dnsmasqfile.write(DNSMASQ_HEADER)
            print("\n" + 20*'#', file=dnsmasqfile)
            for node in self.values():
                dnsmasqfile.write(node.dnsmasq_conf())
        print(f"(Over)wrote {out_filename} from {self.map_filename}")

    def write_hosts(self):
        out_filename = self.out_basename+".hosts"
        with open(out_filename, 'w') as hostsfile:
            hostsfile.write(HOSTS_HEADER)
            for node in self.values():
                hostsfile.write(node.hosts_conf())
            for phy_num in self._missing:
                hostsfile.write(DummyNode(phy_num).dummy_hosts_conf())
        print(f"(Over)wrote {out_filename} from {self.map_filename}")

    def write_diana_db(self):
        out_filename = self.out_basename+"-diana.db"
        with open(out_filename, 'w') as dianafile:
            for node in self.values():
                dianafile.write(node.diana_db())
        print(f"(Over)wrote {out_filename} from {self.map_filename}")


########################################
def main():
    parser = ArgumentParser()
    parser.add_argument("-v", "--verbose", action='store_true', default=False)
    parser.add_argument("-o", "--output", default=None)
    parser.add_argument("-p", "--prep-lab", action='store_true', default=False,
                        help="In prep-lab mode, all nodes are exposed, regardless of the 'slot' column")
    parser.add_argument("-s", "--small", action='store_true', default=False,
                        help="force output of only one node")
    parser.add_argument("input", nargs='?', default='r2lab.map')
    args = parser.parse_args()

    if args.output:
        output = args.output
    elif not args.prep_lab:
        output = args.input.replace(".map", "")
    else:
        output = args.input.replace(".map", "-prep")

    nodes = Nodes(args.input, output, args.prep_lab, args.verbose)
    nodes.load()

    # this is a debugging trick so that we generate only one node,
    # given how loading the JSON file is slow
    if args.small:
        nodes.keep_just_one()

    nodes.write_json()
    nodes.write_dnsmasq()
    nodes.write_hosts()
    if not args.prep_lab:
        nodes.write_diana_db()
    else:
        nodes.write_all_prep_nodes()

    return 0


if __name__ == '__main__':
    exit(main())
