#!/usr/bin/env plcsh

# designed to run directly on r2labapi.inria.fr
# because the API does not expose expired slices (I don't think)

from __future__ import print_function

import psycopg2
import os
import datetime

### helper
def datetime_to_timestamp(dt):
    epoch = datetime.datetime.utcfromtimestamp(0)
    return (dt - epoch).total_seconds()

def today():
    return datetime.datetime.now().strftime("%Y-%m-%d")

### get db password
database = 'planetlab5'
username = 'pgsqluser'
os.system("plc-config --category=plc_db --variable=password > /tmp/dbpassword")
with open("/tmp/dbpassword") as input:
    password = input.read().strip()


######
connection = psycopg2.connect(
    user = username,
    password = password,
    database = database,
)

cursor = connection.cursor()

keynames = "slice_id, name, site_id, created, expires, url, description, creator_person_id"
timestamp_keynames = ['created', 'expires']

request = 'select ' + keynames + ' from slices'
cursor.execute(request)
slice_tuples = cursor.fetchall()

request = 'select * from slice_persons'
cursor.execute(request)
slice_persons = cursor.fetchall()

slice_persons_hash = {chunk[0]: chunk[1]
                      for chunk in slice_persons}

keys = keynames.split(', ')

slices = []

for slice_tuple in slice_tuples:
    slice = {}
    for i, key in enumerate(keys):
        slice[keys[i]] = slice_tuple[i]
    slice_id = slice['slice_id']
    for key in timestamp_keynames:
        slice[key] = datetime_to_timestamp(slice[key])
    slice['person_ids'] = []
    if slice_id in slice_persons_hash:
        slice['person_ids'] = slice_persons_hash[slice_id]
    slices.append(slice)

output="SLICES-{}.json".format(today())

import json

with open(output, 'w') as feed:
    feed.write(json.dumps(slices))
print("(Over)wrote", output)
