# SDR nodes accessible through `fit51`

## overview

* two SDR nodes are attached to fit51, one USRP X310 and one USRP N320.
* each USRP board is connected to fit51 through 2 SFP+ links at 10Gbps.

![](node-51.svg)

* this node is not one of the standard 37 nodes displayed on the web UI on r2lab.inria.fr
* there is currently no easy means to reinstall the node from a (rhubarbe) image.

## power management

please remember to ***SWITCH OFF EVERYTHING BEHIND YOU***  
that means
* the 2 USRP nodes
* as well as the `fit51` node itself

### power management (fit51 node)

| action | command |
|--------|----------|
| turn on | `on-51` |
| turn off | `off-51` |
| reset | `reset-51` |
| status | `status-51` |

### power management (USRP nodes)

both USRP nodes (as well as macphone1 btw) are controlled through a separate old-school PCU
(power-control-unit) Black Box Power Switch 


```console
# make sure to connect to faraday with a `ssh -Y`
firefox http://192.168.1.50 
```

login with `admin` / `adminet++`

**CAUTION:** To switch off the N320 node, run first `ssh root@sdr51 shutdown now`. 

## login

### log into the N320 node

```
sliceX@faraday $ ssh root@sdr51
```

the prompt for that session is `root@ni-n3xx-31B3A77`

### log into fit51

from faraday (of course) :

***Work In Progress***
****

```console
sliceX@faraday $ ssh root@fit51
```

## software configuration

* fedora-32
* podman 1.9.3 + podman-docker (use the `docker` command as usual)

****
***End of Work In Progress***

****
****

## USRP X310

The two network interfaces on fit51 are up by default:

`x310-sfp0` and `x310-sfp1`, both configured with MTU=9000.

To switch on/off the X310 node, you need to use the Black Box Power switch - see above

## USRP N320

The two network interfaces on fit51 are up by default:

`n320-sfp0` and `n320-sfp1`, both configured with MTU=8000.

Another 1Gbps interface is available on the USRP N320 for management. It is known **from
`faraday`** as `sdr51`, connected to the *control* subnet, available from faraday through
`ssh root@sdr51`.

To switch on the X310 node, you need to use the Black Box Power switch - see above

**CAUTION:** To switch off the N320 node, run first `ssh root@sdr51 shutdown now`. 

****
## Configurations
****


### Configurations made on fit51

* all 4 interfaces are 10Gbps SFP+ 


#### /etc/sysconfig/network-scripts/ifcfg-x310-sfp0
```
NAME=x310-sfp0
DEVICE=x310-sfp0
HWADDR=00:0e:1e:79:d7:90
TYPE=Ethernet
ONBOOT=yes
BOOTPROTO=static
IPADDR=10.51.100.1
PREFIX=24
MTU=9000
```
#### /etc/sysconfig/network-scripts/ifcfg-x310-sfp1
```
NAME=x310-sfp1
DEVICE=x310-sfp1
HWADDR=00:0e:1e:79:d7:92
TYPE=Ethernet
ONBOOT=yes
BOOTPROTO=static
IPADDR=10.51.101.1
PREFIX=24
MTU=9000
```
#### /etc/sysconfig/network-scripts/ifcfg-n320-sfp0
```
NAME=n320-sfp0
DEVICE=n320-sfp0
HWADDR=f8:f2:1e:82:d7:c0
TYPE=Ethernet
ONBOOT=yes
BOOTPROTO=static
IPADDR=10.51.200.1
PREFIX=24
MTU=8000
```
#### /etc/sysconfig/network-scripts/ifcfg-n320-sfp1
```
NAME=n320-sfp1
DEVICE=n320-sfp1
HWADDR=f8:f2:1e:82:d7:c1
TYPE=Ethernet
ONBOOT=yes
BOOTPROTO=static
IPADDR=10.51.201.1
PREFIX=24
MTU=8000
```
#### /etc/sysctl.conf
```
net.core.rmem_max=62500000
net.core.wmem_max=62500000
```

### Configurations made on the X310 node

See [https://files.ettus.com/manual/page_usrp_x3x0.html](https://files.ettus.com/manual/page_usrp_x3x0.html)

```
root@fit51 ~ # 

uhd_image_loader --args="type=x300,addr=192.168.10.2,fpga=XG"

/usr/libexec/uhd/usrp_burn_mb_eeprom --values="ip-addr2=10.51.100.2"

/usr/libexec/uhd/usrp_burn_mb_eeprom --values="ip-addr3=10.51.101.2"
```


### Configurations made on the N320 node
See [https://kb.ettus.com/USRP_N300/N310/N320/N321_Getting_Started_Guide](https://kb.ettus.com/USRP_N300/N310/N320/N321_Getting_Started_Guide) 

`root@ni-n3xx-31B3A77:~# uhd_image_loader --args "type=n3xx,fpga=XG"`

#### /etc/systemd/network/sfp0.network


```
    sfp0 (static):
    
  	  [Match]
  	   Name=sfp0
	
  	  [Network]
 	   Address=10.51.200.2/24

 	   [Link]
  	  MTUBytes=8000
```
#### /etc/systemd/network/sfp1.network

```
    sfp1 (static):
    
  	  [Match]
  	   Name=sfp1
	
  	  [Network]
 	   Address=10.51.201.2/24

 	  [Link]
  	   MTUBytes=8000
```
