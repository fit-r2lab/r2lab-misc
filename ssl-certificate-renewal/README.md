# SSL Certificates

## in Chrome

to inspect a certificate, in chrome open the dev tools, then the security tab, there's a button 'inspect certificate'

## the provider

### who

changes all the time; to get the current version:

* go to helpdesk.inria.fr
* find the section 'Demande de certificats numériques'
* make sure to have the VPN enabled if needed
* click 'Documentation en ligne'

### duration

used to be 3 years IIRC at some point, then 2 years, and in 2021 now 1 year; next time 6 months ?

## 2021

## notes for next time

* the csr files under `git/r2lab-misc/ssl-certificate-digicert` are from 2017 but were
  usable as-is in 2019 and 2021, worth keeping them

* reinstallation is rather straightforward but must be done manually on each box,
  depending on the running setup; in particular `r2labapi` has this installed in
  `/etc/planetlab` as the cert for the api and www subsystems.


### the list

| hostname | dest. email |  until      | # |
|----------|-------------|--------------|-------------|
| nbhosting.inria.fr     | nbhosting@inria.fr      | 30 oct 2022 | bMDysN3vdEa4Kr7iCUUg |
| nbhosting-dev.inria.fr | nbhosting@inria.fr      | 30 oct 2022 | 0Uebe0heLoNbvtgbqgFw |
| r2lab.inria.fr         | fit-r2lab-dev@inria.fr  | 30 oct 2022 | XqxAFcs-GkSzTSrJXp0v |
| fit-r2lab.inria.fr     | fit-r2lab-dev@inria.fr  | 30 oct 2022 | 670ddZ521gilXHaRgDEX |
| r2labapi.inria.fr      | fit-r2lab-dev@inria.fr  | 30 oct 2022 | tH1xgQYMoIB3e6l5vjoJ |
| nepi-ng.inria.fr       | fit-r2lab-dev@inria.fr  | 30 oct 2022 | EOvaoLCUN6I0jOIS258s |


## where to install

see https://www.digicert.com/ssl-certificate-installation-nginx.htm

| host | which | where | status |
|------|-------|-------|--|
| nbhosting     | nbhosting     | /root/ssl-certificate/bundle.crt          | OK
| nbhosting     | nbhosting-dev | /root/ssl-certificate-dev/bundle.crt      | OK
| nbhosting-dev | nbhosting     | /root/ssl-certificate/bundle.crt          | OK
| nbhosting-dev | nbhosting-dev | /root/ssl-certificate-dev/bundle.crt      | OK
| r2lab         | r2lab         | /etc/pki/tls/certs/r2lab_inria_fr.crt     | OK
| r2lab         | fit-r2lab     | /etc/pki/tls/certs/fit-r2lab_inria_fr.crt | OK
| r2lab         | nepi-ng       | /etc/pki/tls/certs/nepi-ng_inria_fr.crt   | OK
| r2labapi     | r2labapi_inria_fr.crt        | /etc/planetlab/api_ssl.crt    | KO-KO-KO
| r2labapi     | r2labapi_inria_fr.crt        | /etc/planetlab/www_ssl.crt    | KO-KO-KO
| r2labapi     | r2labapi_inria_interm_fr.crt | /etc/planetlab/api_ca_ssl.crt | KO-KO-KO
| r2labapi     | r2labapi_inria_interm_fr.crt | /etc/planetlab/www_ca_ssl.crt | KO-KO-KO


### notes
* for the nginx and apache setups, the installation is simple
* on the PLC front on the other hand
  * it's easy to have the startup script break it all under your feet
  * so **before restarting** the plc service  
    it's safer to run something like (that's what `/etc/plc,d/httpd` does)
    ```
    cd /etc/planetlab
    openssl verify -CAfile api_ca_ssl.crt api_ssl.crt
    openssl verify -CAfile www_ca_ssl.crt www_ssl.crt
    ```
    which should return OK


## 2019

### the list

| 2019 order # |  until      | dest. email             | hostname               |
|--------------|-------------|-------------------------|------------------------|
|      9778951 | nov 04 2021 | nbhosting@inria.fr      | nbhosting.inria.fr     |
|      9778311 | nov 04 2021 | nbhosting@inria.fr      | nbhosting-dev.inria.fr |
|      9779236 | nov 04 2021 | fit-r2lab-dev@inria.fr  | r2lab.inria.fr         |
|      9779103 | nov 04 2021 | fit-r2lab-dev@inria.fr  | nepi-ng.inria.fr       |
|      9779401 | nov 04 2021 | fit-r2lab-dev@inria.fr  | fit-r2lab.inria.fr     |
|     19068896 | apr 28 2022 | fit-r2lab-dev@inria.fr  | r2labapi.inria.fr      |


### 2 batches

#### main batch of 5 (all but `r2labapi`)

5 first new certificates installed on their respective boxes on 2019 Nov 2

All 5 are valid until ***November 4, 2021***

#### `r2labapi`

that one got forgotten, and had to expire before the openairinterface guys noticed
* ordered on jan. 21 2020
* received on jan 24
