# status

* all 5 switches are configured identically in terms of login/passwd
* the workflow also is the same
  * modify in this repo 
  * `make push-conf` to push on faraday's tftpboot/
  * `copy ...` from /tftpboot into the switch using tftp  
    ***WARNING*** `switch-radio` is a little odd in this respect  
    use the sentence given as comments in the `Makefile`
