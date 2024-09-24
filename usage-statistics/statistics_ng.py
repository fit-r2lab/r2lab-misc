# ---
# jupyter:
#   jupytext:
#     custom_cell_magics: kql
#     text_representation:
#       extension: .py
#       format_name: percent
#   kernelspec:
#     display_name: usage-statistics
#     language: python
#     name: python3
#   language_info:
#     name: python
#     nbconvert_exporter: python
#     pygments_lexer: ipython3
# ---

# %% [markdown]
# # usage data for R2lab
#
# ## Sept. 2024: rewriting this tool from scratch
#
# - we add a `family` tag on the PLCAPI side so that people who register can be tagged with a family;
#   for starters we define the following families
#   - `admin`
#   - `academia/diana`
#   - `academia/fit-slices`
#   - `academia/others`
#   - `industry`
#   - `unknown`
# - in order to bootstrap this, we use
#   - a google spreadsheet with a list of emails and their family, had been maintained manually until now
#   - a few snapshots of slices, that contained the `person_ids`; and this is fortunate because
#     1. when a slice gets deleted it seems like the `person_ids` are lost
#     2. most unfortunately, the event system failed to log the `AddPersonToSlice` events  
#        (this is fixed now, but it's too late for the past)
#
# - based on this information, we tag all slices and persons with one of these families
# - the intended workflow for the future, to have the registrar simply keep track
#   of the family of the person who registers right in the DB, to avoid any
#   separate data source

# %% [markdown]
# ## imports

# %%
from collections import Counter

from pathlib import Path
import json
import getpass

import xmlrpc.client

import pandas as pd

# %% [markdown]
# ## howto load data

# %% [markdown]
# ### load the google sheet

# %%
# this approach is lightweight in terms of authentication
# the target spreadsheet has its sharing policy set as
# 'anyone with the link'

def get_accounts_details():
    SLUG = '1KmbOjhuho9_-BAW1Q8NZSHgRiS0L4jAwXeHsWvOs1Qw'
    URL = (
        'https://docs.google.com/spreadsheets/d/'
        + SLUG
        + '/export?format=csv'
    )
    print(URL)
    return pd.read_csv(URL, index_col='email')

# %% [markdown]
# ### fetch live data at the API

# %% [markdown]
# #### the Family tag
#
# this is created right on the PLCAPI side, in file  
# `/usr/share/plc_api/PLC/Accessors/Accessors_site.py`  
# that does
# ```
# define_accessors(current_module, [Person, Slice], "Family", "family",
#                  "person/slice/ui", "group users into families for usage stats",
#                  set_roles=["admin", "pi"], expose_in_api=True)
# ```

# %% [markdown]
# #### get the password

# %%
URL = "https://r2labapi.inria.fr:443/PLCAPI/"
ACCOUNT = "root@r2lab.inria.fr"
PASSWORD = None

def get_password():
    global PASSWORD
    if PASSWORD is None:
        try:
            with open("password.txt") as input:
                PASSWORD = input.read().strip()
        except FileNotFoundError:
            PASSWORD = getpass.getpass(f"Enter password for {ACCOUNT} : ")
    return PASSWORD

# %%
type Auth = dict[str, str]
type ServerProxy = xmlrpc.client.ServerProxy

def init_proxy() -> tuple[Auth, ServerProxy]:
    auth = {
        'AuthMethod' : 'password',
        'Username'   : ACCOUNT,
        'AuthString' : get_password(),
    }
    return auth, xmlrpc.client.ServerProxy(URL)

def check_password() -> bool:
    auth, proxy = init_proxy()
    try:
        return proxy.AuthCheck(auth) == 1
    except Exception as e:
        print(f"OOPS, something wrong with {type(e)} - {e}")
        return False

# %%
if not check_password():
    raise RuntimeError("Could not authenticate")

# %% [markdown]
# #### get entities

# %%
# thanks to plcapi 7.2.0 this is now something we can retrieve
# from the PLC API
def get_slices():
    auth, proxy = init_proxy()
    cols = ['slice_id', 'name', 'expires', 'person_ids', 'family']
    return proxy.GetSlices(auth, {'DELETED': True, 'EXPIRED': True}, cols)


# %%
def get_persons():
    auth, proxy = init_proxy()
    cols = ['person_id', 'email', 'first_name', 'last_name', 'slice_ids', 'enabled', 'family']
    return proxy.GetPersons(auth, {}, cols)

# %%
def get_leases():
    auth, proxy = init_proxy()
    return proxy.GetLeases(auth)

# %% [markdown]
# ### load slice -> persons

# %% [markdown]
# #### load old SLICES persons
#
# up until sept 2024, the 2 API calls `AddPersonToSlice` and `RemovePersonFromSlice` were not logged in the database !
# for that reason, we need to fetch the old SLICES files to get the list of people in slices at that time

# %%
from collections import defaultdict

type SliceId = int
type PersonId = int

# pass a defaultdict[list] to this function

def load_old_slice_persons(slice_persons: dict[SliceId, list[PersonId]]) -> None:
    def load_one_file(filename):
        with filename.open() as f:
            records = json.load(f)
        for record in records:
            slice_persons[record['slice_id']].extend(record['person_ids'])
    for filename in Path(".").glob("SLICE*.json"):
        load_one_file(filename)



# %% [markdown]
# #### load new SLICES persons
#
# starting sept 2024, we use the events logged by the `AddPersonToSlice` API call

# %%

# pass a defaultdict[list] to this function
def load_new_slice_persons(slice_persons: dict[SliceId, list[PersonId]]) -> None:
    auth, proxy = init_proxy()
    events = proxy.GetEvents(auth, {'call_name': 'AddPersonToSlice'})
    for event in events:
        person_id, sliceid = event['object_ids']
        slice_persons[sliceid].append(person_id)



# %%
def load_slice_persons():
    slice_persons = defaultdict(list)
    load_old_slice_persons(slice_persons)
    load_new_slice_persons(slice_persons)
    return slice_persons


# %% [markdown]
# ## howto clean up the data

# %% [markdown]
# ### slices
#
# not all slices are relevant for the analysis, we need to filter out some that are used for operational purposes

# %%
def slicename_totrash(slicename):
    """
    return True if the slice should be trashed
    """
    site, slug = slicename.split('_', 1)
    match slicename:
        # admin slices
        case 'inria_admin' | 'inria_r2lab.admin' | 'inria_r2lab.nightly':
            return True
        case _:
            return False
    match site:
        # internal PLC slices
        case 'auto':
            return True
        # federation slices
        case 'il8im88ilab' | 'wa8il8im88fe' | 'wa8il8im88ila':
            return True

def clean_slices(slices):
    """
    remove admin and accessory slices
    """
    return [slice for slice in slices if not slicename_totrash(slice['name'])]


# %% [markdown]
# ## actually load data

# %%
accounts_details = get_accounts_details()
print(f"Accounts details: {len(accounts_details)}")
print(accounts_details.head(2))

# %%
slices = get_slices()
print(f"all slices: {len(slices)}")
slices = clean_slices(slices)
print(f"clean slices: {len(slices)}")


# %%

leases = get_leases()
leases.sort(key=lambda l: l['t_from'])
print(f"Leases: {len(leases)}")
persons = get_persons()
print(f"Persons: {len(persons)}")

# %%
slice_persons = load_slice_persons()

print(f"Slice persons: {len(slice_persons)}")


# %% [markdown]
# ---
# xxx to continue from here
#
# ---

# %% [markdown]
# ## tangle entities together

# %% [markdown]
# ### tag persons with a family

# %%
def annotate_persons(persons, accounts_details):
    """
    tag each person with a 'family' field among the ones from the google spreadsheet
    return a Counter object on the family values
    """

    for person in persons:
        try:
            person['family'] = accounts_details.loc[person['email'], 'family']
        except KeyError as e:
            if not person['enabled']:
                person['family'] = 'disabled'
                continue
            print(f"Could not find {person['email']} in the accounts details - classified as 'unknown'")
            person['family'] = 'unknown'

    return Counter(person['family'] for person in persons)


annotate_persons(persons, accounts_details)

# %%
for slice in slices:
    if slice['person_ids']:
        print(slice['name'], slice['person_ids'])


# %%
def annotate_slices(slices, persons):
    """
    tag each slice with a 'family' field, based on the family of the persons in the slice
    """

    persons_by_id = {person['person_id']: person for person in persons}

    for slice in slices:
        families = [persons_by_id[person_id]['family'] for person_id in slice['person_ids']]
        print(f"slice {slice['name']} has families {families}")

annotate_slices(slices, persons)

# %%
