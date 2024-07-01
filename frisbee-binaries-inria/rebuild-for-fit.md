# rebuilding frisbee and imagezip for FIT

## build vm

* created a dedicated build VM in buzzcocks for that purpose only, based on fedora-21-ish

```bash
$ ssh root@buzzcocks.pl.sophia.inria.fr
buzzcocks # lce frisbee
frisbee # cd /build
```

## build requirements

used yum to instal the following packages for static libraries

```bash
yum -y install git make gcc wget tar
yum -y install glibc-static zlib-static openssl-static
```

although this last one probably is not required w/ WITH_CRYPTO=0

## pulling code

On frisbee.pl.sophia.inria.fr

```bash
  cd /build
  git clone git://git-public.flux.utah.edu/emulab-stable.git
  cd emulab-stable
  git checkout master
```

## imagezip

```bash
cd /build/emulab-stable/clientside/os/imagezip/
make -f Makefile-linux.sa WITH_CRYPTO=0
```

* In a first attempt I was not turning off crypto and then I had to add `-ldl` before `-lz` but crypto does not seem like a very useful addition in our case

## frisbee

* Quite identical - same location - same make options
* Ignore OMF patch as the change in client.c does not apply any more
