# reconfigure the switches

## login/passwd

all 5 switches are configured identically in terms of login/passwd

## workflow

here `theswitchname` is one of `control`, `data`, `reboot`, `radio` or `c0007`

### push to faraday

- change the config in this folder (the `switch-theswitchname.conf` file)
- `make push-conf` to push (all) the configs onto faraday's tftpboot/

### push to the switch

- log into the switch from faraday
  ```bash
  ssh switch-theswitchname
  ```
- from the switch's repl, fetch the config file from faraday's tftpboot/ folder
  - `running-config` allows to test the new config without rebooting the switch
  - `startup-config` is the one that will be used after a reboot
- to do so:
  - on the `radio` switch, use `oob_tftp` instead of `tftp`
  ```bash
  # warning, on switch-radio we need to use oob_tftp (wtf?)
  #
  # copy oob_tftp://192.168.4.100/switch-radio.conf running-config
  # copy oob_tftp://192.168.4.100/switch-radio.conf startup-config
  ```
  - on the other switches, uses `tftp` like so
  ```bash
  # once you have made a make push you can run from the switch something like e.g.
  #
  # copy tftp://192.168.4.100/switch-c007.conf running-config
  # copy tftp://192.168.4.100/switch-c007.conf startup-config
  #
  # copy tftp://192.168.4.100/switch-data.conf running-config
  # copy tftp://192.168.4.100/switch-data.conf startup-config
  #
  # copy tftp://192.168.4.100/switch-control.conf running-config
  # copy tftp://192.168.4.100/switch-control.conf startup-config
  #
  # copy tftp://192.168.4.100/switch-reboot.conf running-config
  # copy tftp://192.168.4.100/switch-reboot.conf startup-config
  ```
- still from the switch, reload the config with
  ```bash
  reload
  ```

### save your work

once you're happy, do not forget to save, commit and push  
so that your changes will be available for the next change

## misc notes

- as of 2025 March, faraday can no longer ssh into the switches  
  ```bash
  # ssh switch-control
  ssh_dispatch_run_fatal: Connection to 192.168.4.103 port 22: error in libcrypto
  ```
- this appears to be due to an OS upgrade (fedora41) that comes with stricter security settings
- in order to circumvent that, I did
  ```
  update-crypto-policies --set LEGACY
  ```
- here are a few relevant links;   
  - https://serverfault.com/questions/1125843/error-in-libcrypto-connecting-rhel-9-server-to-centos-6-via-sftp-ssh
  - https://rwmj.wordpress.com/2022/08/08/ssh-from-rhel-9-to-rhel-5-or-rhel-6/
- there seemed to be no good way to tweak this only for a specific subset of nodes;  
  the most relevant recipe would have required to use a sentence like
  ```bash
  OPENSSL_CONF=/var/tmp/openssl.cnf ssh rhel5or6-host
  ```
  which, well, is not really practical in our case
