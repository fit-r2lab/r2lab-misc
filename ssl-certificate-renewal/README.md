# SSL Certificates

<style>
.red {color: red;}
.orange {color: orange;}
.green {color: green;}
</style>

## Update may 2025 - for bigjohn / portainer

```{admonition} Long story short

as long as SSL certificates are concerned, there is **no need to worry about bigjohn** and its containers anymore;

after a lot of back and forth, longjohn now uses a setup with caddy and all 3
certificates (portainer, copilot, limesurvey) are now totally auto0-generated
and auto-renewed by caddy
```

if/when that makes sense we could use that same approach to run the grafana,
prometheus, and all other services in that box


## Update november 2024

when rebuilding r2lab and r2labapi, we have turned on the `/etc/dsissl` service,
which is advertised as being able to auto-renew the certificates (maybe based on
certbot or similar ?); in any case, at this point, we should no longer need to
worry about

- nepi-ng
- r2lab
- r2labapi
- r2lab-sidecar

so for next upgrade in 2025 (or before), take that chance to use dsissl on
nbhosting and nbhosting-dev as well, that would be just great !

## in Chrome

to inspect a certificate, in chrome open the dev tools, then the security tab, there's a button "*inspect certificate*"

## NOTE on naming

* downloaded certs end in `.pem` (or `.cer`, in one instance, see below)
* while in many cases, the cert file to use is configured as a `*.crt`

so as of 2023 what I try to do is

* keep the same name for the new cert file as the one given when downloading it from renater - to avoid tedious renamings
* create symlinks to the old (configured) names

## note on formats

* `.pem` files  
  in all remaining cases (i.e. when using nginx), pick the second format in the list, the one that says
  > as Certificate (w/ issuer after), PEM encoded

***

## where to install

see also https://www.digicert.com/ssl-certificate-installation-nginx.htm

| host | certificate | where | status | 
|------|-------------|-------|--------|
| nbhosting     | nbhosting                       | /root/ssl-certificate/            | OK |
| nbhosting     | nbhosting-dev                   | /root/ssl-certificate-dev/        | OK |
| nbhosting-dev | nbhosting                       | /root/ssl-certificate/            | OK |
| nbhosting-dev | nbhosting-dev                   | /root/ssl-certificate-dev/        | OK |
| r2lab         | r2lab                           | /etc/pki/tls/certs/               | dsissl - no longer needed |
| r2lab         | nepi-ng                         | /etc/pki/tls/certs/               | dsissl - no longer needed |
| r2lab         | r2lab-sidecar                   | /etc/pki/tls/certs/               | dsissl - no longer needed |
| r2labapi      | r2labapi_inria_fr.crt           | /etc/planetlab/                   | dsissl - no longer needed |
| r2labapi      | r2labapi_inria_interm_fr.crt    | /etc/planetlab/                   | dsissl - no longer needed |
| --not-yet--   | sopnode-registry                | n/a | |

## update 2024 Oct 4

* [x] nbhosting.inria.fr
* [x] nbhosting-dev.inria.fr
* [x] r2lab.inria.fr
* [x] nepi-ng.inria.fr
* [x] r2lab-sidecar.inria.fr
* [x] r2labapi.inria.fr
* [ ] sopnode-registry.inria.fr - not installed as the VM is not yet available

## update 2023 Oct 14

* created keystone ticket when asking for help  
  <https://support.inria.fr/SelfService/Display.html?id=283625>
* Loic Sirvin pointed me to an easy-to-use dashboard with all my certs and their
  status, just needed to click to ask for a renewal  
  <https://cert-manager.com/customer/Renater/ssl/XKzRdsNymTdU1QsC6r7a/list>
* did it for
  * [x] nbhosting.inria.fr
  * [x] nbhosting*dev.inria.fr
  * [x] r2lab.inria.fr
  * [x] nepi-ng.inria.fr
  * [ ] r2labapi.inria.fr
  * [ ] r2lab-sidecar.inria.fr
  * [ ] sopnode-registry.inria.fr

## the details

### who (the provider)

changes all the time; to get the current version:

* go to `helpdesk.inria.fr`
* find the section "***Demande de certificat de service***"
* make sure to have the VPN enabled if needed
* click "***Documentation en ligne***"

### duration

used to be 3 years IIRC at some point, then 2 years, and in 2021 now 1 year;
next time 6 months ?

***

## early 2023: r2lab-sidecar

### the need

for robustness and firewall traversals, we want to move the sidecar service

* from r2lab.inria.fr:999
* to r2lab-sidecar.inria.fr:443

which leads to the new requirement for a certificate that validates this DNS
name

### the CSR (and key)

```shell
cd 2023-early/r2lab-sidecar
SERVICE_NAME=r2lab-sidecar.inria.fr
openssl req -newkey rsa:2048 -keyout $SERVICE_NAME.key -out $SERVICE_NAME.csr -nodes -sha256 -subj "/CN=$SERVICE_NAME"
```

### the format

the target app that uses the certificate is our Python `sidecar-server.py` the
format to use for installing the cert should be the same as for nginx, since
before this move we were using the same cert for both the official website at
`r2lab.inria.fr` and for the websockets service on 999

***

## 2022

<https://cert-manager.com/customer/Renater/ssl>

### the list

| hostname | dest. email | status | comment |
|----------|-------------|---|---------|
| `r2lab.inria.fr`            | fit-r2lab-dev@inria.fr  | <span class=green>oct 14 2023</span> | alternate-name `fit-r2lab.inria.fr` <br> ***nginx-based***
| `r2labapi.inria.fr`         | fit-r2lab-dev@inria.fr  | <span class=green>oct 14 2023</span> | first form (certificate in pem format) <br>3 files `.crt` in `/etc/planetlab` to change identically
| `nepi-ng.inria.fr`          | fit-r2lab-dev@inria.fr  | <span class=green>oct 14 2023</span> | ***nginx-based***
| `sopnode-registry.inria.fr` | fit-r2lab-dev@inria.fr  | <span class=green>oct 14 2023</span> | bundle pem needed; not a PKCS#7, not an intermediate
| `nbhosting.inria.fr`        | nbhosting@inria.fr      | <span class=green>oct 14 2023</span> | ***nginx-based*** (see note)
| `nbhosting-dev.inria.fr`    | nbhosting@inria.fr      | <span class=green>oct 14 2023</span> | ***nginx-based*** (see note)
|

for ***nginx-based sites***, among the formats available in the mail, I pick
> "***as Certificate (w/ issuer after), PEM encoded***"

which is the second one

### the `fit-r2lab.inria.fr` case

formerly with apache it was simple : one certificate per hostname; now with
`nginx`, the same approach requires to create one server per hostname, with all
the attached settings duplicated

so it seems to be time to play with SAN (server alternate name) csr requests

* the new `csr` was generated in `fit+r2lab-csr/` using this command

  ```bash
  openssl req -config fit+r2lab.conf -new -sha256 -newkey rsa:2048 -keyout fit+r2lab.key -out fit+r2lab.csr -nodes
  ```

* the old `csr` files are renamed into `.obso` and moved in the `2021/` folder

### NOTE (the accident)

about `sopnode-registry.inria.fr`
* I made a first request valid up to Sept. 26 2023
* stored in folder `2022/sopnode-registry-v0`
* ***together with the key***
* however I did not have time to deploy it yet, so let us have all them in sync
* which means, throw that one away and ask for a new one

***

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

