# Operations Guide

## BIOS Settings

The BIOS installed is Phoenix SecureCore, version LV-67N Ver: 1.2; procedure to upgrade the BIOS still in the old google drive, together with the manufacturer's doc BTW

### Magic keys

* Use these keys right after you listen to the first BEEP;
* when taken into account you'll hear a second BEEP to acknowledge
  * `<DEL>` to reach the BIOS menu
  * `<F5>` to reach the boot menu

### R2lab BIOS settings:

* RESET to factory defaults
* Configure time
* Main -> Boot Features
  * quick boot enabled
* Advanced-> HDD configuration
  * IDE mode
* Advanced->Network configuration
  * LAN OPROM Enabled
* Boot order :
  1. the 2nd Lan interface (something like PCI LAN2)
  1. then hard drive (ssd in fact)

### Notes on IDE *vs* AHCI

The `pxefrisbee` image does not contain the required drivers to be able to write on AHCI; that's why we are left with only the option to run IDE for now.

# Issues with nodes at R2lab
The present document aims to document all know/common bugs and issues related to the nodes located at R2lab platform (faraday).

## EI.002
The node does not answer for the command "off" or "curl 192.168.1.xx/off" in faraday terminal.

#### How to deal with
* A double command (off [enter]; off [enter]) will surcharge the CM and the node will process the off. The answer in terminal could be "CM card busy".
* A physical reset in the CM card is mandatory. Disconnect the power cable, wait for a while, and connect again. MUST reconfigure the BIOS. See google docs for the BIOS setup.
* One simpler way to achieve this in the chamber is to use the wall power control panel to turn all the nodes on and off in a single move.


## EI.003
The node does not receive - or at least react - upon the "on" message.
The blue light is switch on, however, the trigger to start the node never happens when I send the command to do it.

#### How to deal with
- No solution, yet...


## EI.004
The node takes to much time to load and fails to start the O.S.

#### How to deal with
- The BIOS configuration for some reason was lost. Mainly the *Quick Setup* option. See google docs to have the BIOS setup.


****
****
****

# Problem detected
We have two nodes (#4 and #18) that do not execute the remote command RESET after a while when turned on.
It means that when we sent the RESET command thought the network the command is not executed at all.

# How it happens
After a while turned on, the node do not responds anymore the remote RESET command.

# How to reproduce
Considering the node in OFF state, with no energy cable plugged for at least 5 minutes.
Plug the energy cable, start the node using ON remote command. Once did, the remote command RESET will work
properly for ~ 3min. After this period, the node do not respond anymore to the RESET remote command.
To get the remote RESET command working again, it is obligatory remove the energy cable and leave the node unplugged for ~5min. or more.

# Tests made
In order reproduced and detect the problem we removed both nodes from the anechoic chamber and placed them at our lab.
Then, we setup both nodes using only:
- Energy cable
- On/Off/Reset wired network cable

## 1 - physical reset
- A remote ON command was sent. (PASS)
- RESET physically many times. (PASS)
- A remote OFF command was sent. (PASS)

## 2 - starting node after no cables plugged
- All cables unplugged.
- All cables plugged, after ~5min.
- A remote ON command was sent. (PASS)
- A remote RESET command was sent after 10sec, 20sec, 30sec and 1min. (PASS)
- A remote RESET command was sent after 3min. (FAIL)
- A remote OFF command was sent. (PASS)

  ## 2.1 - after a while from the last OFF command in test #2
  - A remote ON command was sent. (PASS)
  - A remote RESET command was sent after 10sec, 20sec, 30sec and 1min. (FAIL)
  - A remote RESET command was sent after 3min. (FAIL)
  - A remote OFF command was sent. (PASS)

## 3 - starting node after removing Energy cable
- Energy cable unplugged (On/Off/Reset cable plugged).
- Energy cable plugged, after ~5min.
- A remote ON command was sent. (PASS)
- A remote RESET command was sent after 10sec, 20sec, 30sec and 1min. (PASS)
- A remote RESET command was sent after 3min. (FAIL)
- A remote OFF command was sent. (PASS)

  ### 3.1 - after a while from the last OFF command in test #3
  - A remote ON command was sent. (PASS)
  - A remote RESET command was sent after 10sec, 20sec, 30sec and 1min. (FAIL)
  - A remote RESET command was sent after 3min. (FAIL)
  - A remote OFF command was sent. (PASS)

  ### 3.2 - physically reset
  - A remote ON command was sent. (PASS)
  - RESET physically many times. (PASS)
  - A remote OFF command was sent. (PASS)

## 4 - starting node after removing On/Off/Reset cable
- On/Off/Reset cable unplugged (energy cable plugged), after ~5min.
- On/Off/Reset cable plugged.
- A remote ON command was sent. (PASS)
- A remote RESET command was sent after 10sec, 20sec, 30sec and 1min. (FAIL)
- A remote RESET command was sent after 3min. (FAIL)
- A remote OFF command was sent. (PASS)

  ### 4.1 - trying again after a while from the last OFF command in test #4
  - A remote ON command was sent. (PASS)
  - A remote RESET command was sent after 10sec, 20sec, 30sec and 1min. (FAIL)
  - A remote RESET command was sent after 3min. (FAIL)
  - A remote OFF command was sent. (PASS)

  ### 4.2 - physically reset
  - A remote ON command was sent. (PASS)
  - RESET physically many times. (PASS)
  - A remote OFF command was sent. (PASS)

# Update in hardware
Concerning the hardware, in a solution try, two actions were made:
- We replaced partially the CMC card.
  CMC card is composed by an Arduino board + another circuit affixed on top. We were not able to replace the second component because we don't have a backup of this card for now.
- Burned again the firmware

No different result appeared as answer of these changes. The node behavior was exactly the same as described before.

# Some infos about it
Turn the node off without unplugged the energy cable do not make any effect in remote RESET command.
In any phase of the tests, all others basic commands worked properly (On, Off, Load) on the node.
More than once in the tests, at some point, the node was switched off and a physical RESET button was placed. In all these cases the RESET worked perfectly. Even when the energy cable remained plugged.

# Conclusion
The physically reset, when applied, always worked fine in the node.
The remote ON/OFF command always worked fine.
Seems the Arduino card after a while (~ 3min) do not answer anymore to the remote RESET command.
