# the v0 nodes

as of end nov. 2025, in L102B aka V0, we have the following nodes  
note that the status is approximate, we have not conducted any heavy duty tests, but a few attempts at rload'ing them

## fully functional

- ***13***: OK
- ***42***: OK

## so-so

- ***04***: sometimes works, but unreliably

## half working

- ***31***: receptive to CMC commands, starts to rload, but fails approximately at 40% when rloading the default (ubuntu-22) image:
- ***18***: receptive to CMC commands, starts to rload, but fails approximately at 40% when rloading the default (ubuntu-22) image:

```
10:04:07 - +043s: fit31 {'ip': '192.168.3.31', 'frisbee_error': 'Something went wrong with frisbee (short write...)'}
10:04:07 - +043s: fit18 {'ip': '192.168.3.18', 'frisbee_error': 'Something went wrong with frisbee (short write...)'}
```

## badly broken

- ***40***: second interface does not show up, either in BIOS nor in linux a fortiori
- ***39***: does

## lost track of...

the following nodes are yet to be located

11,15,37
