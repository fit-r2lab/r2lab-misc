#!/usr/bin/env plcsh

# designed to run directly on r2labapi.inria.fr

from __future__ import print_function

import time

def printable_time(epoch):
    return time.strftime("%Y %m %d", time.localtime(epoch))

ps = GetPersons()
ps.sort(key = lambda p: p['date_created'])

def list_accounts():
    for p in ps:
        print(printable_time(p['date_created']), "id={:03d}".format(p['person_id']), p['email'])

import sys

with open('ACCOUNTS', 'w') as sys.stdout:
    list_accounts()
