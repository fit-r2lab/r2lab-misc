# status

* all 5 switches are configured identically in terms of login/passwd
* the workflow also is the same
  * modify in this repo 
  * `make push-conf` to push on faraday's tftpboot/
  * `copy ...` from the switch using tftp
* **except** that for now `switch-radio` is WIP
  * its config is consistent with `switch-radio.conf`
  * **however** for some reason I cannot copy through tftp from the switch
  * the odd thing actually is
    * I can ping from faraday to switch-radio
    * BUT I cannot ping 192.168.4.100 from switch-radio
    * and in that scenario there is even nothing that comes in faraday
    * ... to be investigated later on
