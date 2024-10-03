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
#   - `academia/slices`
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

FORMAT_DATE_TIME = "%Y-%m-%d %H:%M:%S"


# %% [markdown]
# ## families
#
# when a slice has (person from) several families, as a best guess we can tag it with the most relevant one

# %%
# pick the highest-ranking among this list

ORDERED_FAMILIES = [
    "unknown",
    "admin",
    "academia/diana",
    "academia/slices",
    "academia/others",
    "industry",
]

def relevant_family(families: set[str]):
    map = dict((x, y) for (y, x) in enumerate(ORDERED_FAMILIES))
    indices = {map.get(family.lower(), -1) for family in families}
    # print(indices)
    if -1 in indices:
        print(f"WARNING: unknown family within {families}")
        indices.remove(-1)
    index = max(indices, default=0)
    return ORDERED_FAMILIES[index]


TESTS = [
    (["admin", "academia/diana"], -1),
    (["admin", "academia/slices"], -1),
    (["academia/slices", "academia/others"], -1),
    (["admin", "industry"], -1),
    (["admin", "unknown"], 0),
    (["ACADEMIA/diana", "academia/slices"], -1),
    (["ACADEMIAsdf/diana", "academia/slices"], -1),
    (["ACADEMIAsdf/diana"], "unknown"),
    (["academia/diana", "academia/others"], -1),
    (["academia/diana", "industry"], -1),
    (["academia/diana", "unknown"], 0),
    (["academia/slices", "academia/others"], -1),
    (["academia/slices", "industry"], -1),
    (["academia/slices", "unknown"], 0),
    (["academia/others", "industry"], -1),
    (["academia/others", "unknown"], 0),
    (["industry", "unknown"], 0),
    (["unknown", "unknown"], 0),
]

def test_relevant_family():
    for (arg, expected) in TESTS:
        if isinstance(expected, int):
            expected = arg[expected]
        result = relevant_family(arg)
        if result != expected:
            print(f"test {arg} -> {result} (expected {expected})")
    print("test_relevant_family done")

test_relevant_family()


# %% [markdown]
# ## manual classification tools

# %% [markdown]
# ### slices
#
# not all slices are relevant for the analysis, we can tag some as 'admin'

# %%
def is_admin_slice(slicename):
    """
    return True if the slice should be trashed
    """
    site, slug = slicename.split('_', 1)
    match slicename:
        # admin slices
        case (
              'inria_admin'
            | 'inria_r2lab.admin'
            | 'inria_r2lab.nightly'
            | 'inria_r2lab.tutorial'
            | 'inria_mario_maintenance'
        ):
            return True
    match site:
        # internal PLC slices
        case 'auto':
            return True
        # federation slices
        case 'il8im88ilab' | 'wa8il8im88fe' | 'wa8il8im88ila':
            return True
    return False



# %%
is_admin_slice('wa8il8im88fe_g8r5PimGIgMYfd')

# %% [markdown]
# ### hard-wired slice -> family

# %%
SLICE_FAMILIES = {
    'inria_oai.build': 'academia/slices',
    'inria_mario.maintenance': 'admin',
    'inria_mario.script': 'academia/diana',
    'inria_wifi.sdn': 'academia/diana',
    'inria_oai.b210' : 'academia/diana',
    'inria_walid.demo': 'academia/diana',
    'unicamp_wifisdn.slicesdn' : 'academia/others',
    'inria_iotlab.iotlab_slice' : 'academia/diana',
    'inria_anas.ping': 'academia/diana',
    'inria_mesh.routing': 'academia/diana',
    'inria_oai.skype': 'academia/diana',
    'inria_es': 'academia/diana',
    'inria_fehland1': 'academia/diana',
    'inria_yassir': 'academia/diana',
    'inria_oai.slicing': 'academia/slices',
    'inria_visit': 'academia/diana',
    'eurecoms3_coexist': 'academia/slices',
    'inria_urauf': 'academia/diana',
    'eurecoms3_today': 'academia/slices',
    'inria_jawad': 'academia/diana',
    "inria_sopnode": "academia/slices",
    "inria_iotlab.iotlab_slice": "academia/slices",
 }


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
# #### note on the Family tag
#
# for each person and each slice, we store a 'family' attibute that classifies them in one of the above categories
#
# this is done by the `family` tag in the PLCAPI, which allows to kind of dynamically extend the data model
#
# in is created right on the PLCAPI side, in file
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

print("Authentication successful")

# %% [markdown]
# #### get entities

# %%
# thanks to plcapi 7.2 this is now something we can retrieve
# from the PLC API, including the deleted and expired ones

# also in order to retrieve the 'family' tag we need to add it
# explicitly to the columns parameter

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
def get_events():
    auth, proxy = init_proxy()
    return proxy.GetEvents(auth, {'call_name': 'AddPersonToSlice'})


# %%
# expose a dataframe ready to be concatenated with the LEASES-EARLY dataframe
def get_leases_df():
    auth, proxy = init_proxy()
    leases = proxy.GetLeases(auth)
    leases_df = pd.DataFrame(leases)[LEASES_COLUMNS1]
    leases_df['beg'] = pd.to_datetime(leases_df['t_from'], unit='s')
    leases_df['end'] = pd.to_datetime(leases_df['t_until'], unit='s')
    leases_df.drop(columns=['t_from', 't_until'], inplace=True)
    return leases_df

# %% [markdown]
# ### how to load the early leases
#
# some point in time circa march 2018, as part of some maintenance cleanup, the unique node has been renamed
# from `37nodes.r2lab.inria.fr` to `faraday.inria.fr`;
# at least that's my conjecture, because GetLeases() has data only from about that time
#
# so in this part we are doing some archeology in the Events database to recover the missing leases, and focus on the ones that were attached to the old nodename
#
# the result is stored in a file `LEASES-EARLY.csv` that we can load here for further iterations

# %%
EARLY_LEASES = "LEASES-EARLY.csv"
# as epoch
LEASES_COLUMNS1 = ['lease_id', 'hostname', 'name', 't_from', 't_until']
# as datetime
LEASES_COLUMNS2 = ['lease_id', 'hostname', 'name', 'beg', 'end']

# %% [markdown]
# #### the AddLease events formats
#
# we fetch the `AddLeases` events and inspect their `call` and `message` fields; so we need to parse that

# %%
# there are several formats for the event's call field

call_samples = [
    "AddLeases[{'AuthMethod': 'password', 'AuthString': 'Removed by API', 'Username': 'root@r2lab.inria.fr'}, ['37nodes.r2lab.inria.fr'], 'inria_oai.build', 1474542000, 1474556400]"
    , # or
    "AddLeases[{'AuthMethod': 'password', 'AuthString': 'Removed by API', 'Username': 'root@r2lab.inria.fr'}, ['37nodes.r2lab.inria.fr'], 'inria_oai.build', '2016-12-19 14:00:00', '2016-12-19 15:00:00']"
    , # or
    "AddLeases[{'AuthMethod': 'password', 'AuthString': 'Removed by API', 'Username': 'root@r2lab.inria.fr'}, [1], 'inria_r2lab.nightly', 1606615200, 1606618800]"
]

message_samples = [
    "New leases [1450L] on n=[u'37nodes.r2lab.inria.fr'] s=inria_oai.build [2016-09-22 11:00:00 UTC -> 2016-09-22 15:00:00 UTC]"
    , # or
    "New leases [] on n=[] s=inria_pepr01 [2024-08-19 13:00:00 UTC -> 2024-08-19 14:00:00 UTC]"
]

# turns out the last format has only been used for the nightly slice
# so we could just have ignored it, but well we didn't know that before we parsed it

# %% [markdown]
# #### parse the AddLease event call format

# %%
import re

re_between_quotes = re.compile(r".*'([^']*)'.*")
re_int_in_brackets = re.compile(r".*\[(\d+)\].*")
re_digits_only = re.compile(r"(\d+)[^\d]*$")
re_date = re.compile(r"^[^\d]*(\d+-\d+-\d+)$")
re_time = re.compile(r"^(\d+:\d+:\d+)[^\d]*$")
re_new_lease = re.compile(r"New leases \[(\d+).*")


def parse_addlease_event(call, message):
    try:
        # if this fails, the call has failed - ignore this event
        lease_id = int(re_new_lease.match(message).group(1))
    except AttributeError as e:
        return None, None, None, None, None
    try:
        *_, nodepart, slicepart, frompart, topart = call.split()
        if match := re_digits_only.match(topart):
            # FORMAT 1
            end = pd.to_datetime(match.group(1), unit="s")
            beg = pd.to_datetime(int(re_digits_only.match(frompart).group(1)), unit="s")
        else:
            *_, nodepart, slicepart, fromdate, fromtime, todate, totime = call.split()
            from_string = (
                re_date.match(fromdate).group(1)
                + " "
                + re_time.match(fromtime).group(1)
            )
            to_string = (
                re_date.match(todate).group(1) + " " + re_time.match(totime).group(1)
            )
            beg = pd.to_datetime(from_string, format=FORMAT_DATE_TIME)
            end = pd.to_datetime(to_string, format=FORMAT_DATE_TIME)
        slicename = re_between_quotes.match(slicepart).group(1)
        if match := re_between_quotes.match(nodepart):
            nodename = match.group(1)
        else:
            nodename = re_int_in_brackets.match(nodepart).group(1)

        return lease_id, nodename, slicename, beg, end
    except Exception as e:
        print(
            f"OOPS: could not parse AddLease event, got exceptions {type(e)}: {e} with call\n"
            f"{call}\n"
            f"and message\n"
            f"{message}"
        )
        return None, None, None, None, None


def test_parse_addlease_event():
    for sample in call_samples:
        for message in message_samples:
            print(parse_addlease_event(sample, message))

# test_parse_addlease_event()


# %%
# retrieve all the events

def retrieve_added_leases():

    auth, proxy = init_proxy()
    lease_events = proxy.GetEvents(auth, {'call_name': 'AddLeases'})
    df_lease_events = pd.DataFrame(lease_events)

    # parse all calls, returns a Series of tuples
    series = df_lease_events.apply(lambda row: parse_addlease_event(row['call'], row['message']), axis=1)
    # transform into a proper dataframe; use same names as in the API
    as_df = pd.DataFrame(series.tolist(), columns=LEASES_COLUMNS2)
    # keep only the ones corresponding to the historical hostname
    as_df = as_df.loc[as_df.hostname == '37nodes.r2lab.inria.fr']
    # there are some undefined lease_ids before we filter on the hostname
    as_df['lease_id'] = as_df['lease_id'].astype(int)
    return as_df


# %% [markdown]
# #### the UpdateLease events formats

# %%
call_samples = [
    "UpdateLeases[{'AuthMethod': 'password', 'AuthString': 'Removed by API', 'Username': 'root@r2lab.inria.fr'}, [3501], {'t_from': '2016-12-19 07:00:00', 't_until': '2016-12-19 09:00:00'}]"
    , # or
    "UpdateLeases[{'AuthMethod': 'password', 'AuthString': 'Removed by API', 'Username': 'root@r2lab.inria.fr'}, [4183], {'t_from': 1490623200, 't_until': 1490628600}]"
    , # or
    "UpdateLeases[{'AuthMethod': 'password', 'AuthString': 'Removed by API', 'Username': 'root@r2lab.inria.fr'}, [3660], {'t_until': 1484057400}]"
]

# %%
re_update_lease = re.compile(
    r".*\[(?P<lease_id>\d+)\], {('t_from': ('(?P<from_str>.*)'|(?P<from_num>\d+)), )?'t_until': ('(?P<until_str>.*)'|(?P<until_num>\d+)).*"
)

def parse_updatelease_event(call):
    try:
        match = re_update_lease.match(call)
        lease_id = int(match.group('lease_id'))
        if match.group('from_str'):
            beg = pd.to_datetime(match.group('from_str'), format='ISO8601')
        elif match.group('from_num'):
            beg = pd.to_datetime(int(match.group('from_num')), unit='s')
        else:
            beg = None
        if match.group('until_str'):
            end = pd.to_datetime(match.group('until_str'), format='ISO8601')
        elif match.group('until_num'):
            end = pd.to_datetime(int(match.group('until_num')), unit='s')
        else:
            end = None
        return lease_id, beg, end
    except Exception as e:
        print(f"OOPS: could not parse UpdateLease event, got exceptions {type(e)}: {e} with call\n{call}")
        return None, None, None

def test_parse_updatelease_event():
    for sample in call_samples:
        print(parse_updatelease_event(sample))

test_parse_updatelease_event()

# %% [markdown]
# #### parse the UpdateLease event call format

# %%
additions = retrieve_added_leases()

# %%
additions.head(2)


# %%
def retrieve_updated_leases(additions):
    auth, proxy = init_proxy()
    lease_events = proxy.GetEvents(auth, {'call_name': 'UpdateLeases'})
    df_lease_events = pd.DataFrame(lease_events)
    # parse all calls, returns a Series of tuples
    series = df_lease_events.apply(lambda row: parse_updatelease_event(row['call']), axis=1)
    # transform into a proper dataframe; use same names as in the API
    changes = pd.DataFrame(series.tolist(), columns=['lease_id', 'beg', 'end'])
    # keep only last record for each lease_id
    changes = changes.groupby('lease_id').last()
    # apply changes
    additions.update(changes)
    # just in case
    return changes



# %% [markdown]
# #### remove overlaps

# %%
def overlap(b1, e1, b2, e2):
    """
    returns True if the two intervals [b1, e1] and [b2, e2] overlap
    """
    return b1 < e2 and b2 < e1

def test_overlap():
    tests = [
        (False, (1, 2, 3, 4)),
        (False, (3, 4, 1, 2)),
        (False, (1, 2, 2, 3)),
        (False, (2, 3, 1, 2)),
        (True, (1, 3, 2, 4)),
        (True, (2, 4, 1, 3)),
        (True, (1, 4, 2, 3)),
        (True, (2, 3, 1, 4)),
    ]
    for (expected, args) in tests:
        result = overlap(*args)
        # if result != expected:
        print(f"with {args=}, expected {expected} got {result}")

# test_overlap()



# %%

def remove_overlaps(df):
    # starting from the end and moving backbards
    # we keep the last one and consider it the 'reference'
    # then we consider the previous one (so the last but one)
    # if it overlaps, we discard it
    # otherwise we keep it and it becomes the reference
    # and so on
    # this by essence is iterative, so I can't see a way to write it vectorized
    #
    # note that a code that would look at this problem
    # along the following lines does not do the same thing !
    #
    # df['previous_end'] = df['end'].shift(1)
    # df['overlap'] = df['previous_end'] > df['beg']
    # overlap = df.loc[df.overlap]
    #
    df.sort_values(by='end', ascending=False, inplace=True)
    # create tmp column
    df['discard'] = False
    ref = None
    # we must skip the first one
    first = True
    for idx, row in df.iterrows():
        if first:
            first = False
            ref = row
            continue
        if not overlap(row['beg'], row['end'], ref['beg'], ref['end']):
            # no overlap
            ref = row
        else:
            # cannot update through row...
            df.loc[idx, 'discard'] = True
            print((df.loc[idx]))
    df.drop(df[df.discard].index, inplace=True)
    df.drop(columns=['discard'], inplace=True)
    df.sort_values(by='beg', ascending=True, inplace=True)
    return df


# %% [markdown]
# #### old leases: putting it all together

# %%
# use cached data if available

def load_old_leases():
    if Path(EARLY_LEASES).exists():
        df = pd.read_csv(EARLY_LEASES)
        df['beg'] = pd.to_datetime(df['beg'], format='ISO8601')
        df['end'] = pd.to_datetime(df['end'], format='ISO8601')
        return df
    else:
        # get additions from events
        old_leases = retrieve_added_leases()
        # take into account updates
        retrieve_updated_leases(old_leases)
        # remove overlaps
        remove_overlaps(old_leases)
        # remove duplicates, many leases are found under 2 different lease_ids
        old_leases.drop_duplicates(
            subset=('name', 'beg', 'end'), keep='first', inplace=True)
        old_leases.to_csv(EARLY_LEASES, index=False)
        return old_leases


# %%
load_old_leases().dtypes

# %% [markdown]
# ## how to attach slice -> persons

# %%
from collections import defaultdict

type SliceId = int
type PersonId = int

# pass a defaultdict[list] to the following functions

# %% [markdown]
# #### use current database
#
# the unexpired slices have a person_ids attribute that contains the list of persons in the slice

# %%
def update_slice_persons_from_slices(slice_persons, slices):
    for slice in slices:
        slice_id = slice['slice_id']
        if slice['person_ids']:
            slice_persons[slice_id].extend(slice['person_ids'])


# %% [markdown]
# #### use snapshot SLICES*.json files
#
# up until sept 2024, the 2 API calls `AddPersonToSlice` and `RemovePersonFromSlice` were not logged in the database !
# for that reason, we need to fetch the old SLICES files to get the list of people in slices at that time

# %%
def update_slice_persons_from_files(slice_persons, paths):
    for path in paths:
        with path.open() as feed:
            data = json.load(feed)
            for slice in data:
                slice_id = slice['slice_id']
                person_ids = slice['person_ids']
                if person_ids:
                    slice_persons[slice_id].extend(person_ids)


# %% [markdown]
# #### load new SLICES persons
#
# starting sept 2024, we use the events logged by the `AddPersonToSlice` API call

# %%
def update_slice_persons_from_events(slice_persons, events) -> None:
    auth, proxy = init_proxy()
    for event in events:
        person_id, sliceid = event['object_ids']
        slice_persons[sliceid].append(person_id)


# %% [markdown]
# #### all together

# %%
def load_slice_persons(slices, events):
    slice_persons = defaultdict(list)
    update_slice_persons_from_slices(slice_persons, slices)
    print(f"after using the database, got {len(slice_persons)} slices")
    update_slice_persons_from_files(slice_persons, Path(".").glob("SLICES*.json"))
    print(f"after loading SLICES*.json files, got {len(slice_persons)} slices")
    update_slice_persons_from_events(slice_persons, events)
    print(f"after scanning Events, got {len(slice_persons)} slices")
    return slice_persons


# %% [markdown]
# ## actually load data

# %%
# from the google spreadsheet

accounts_details = get_accounts_details()
print(f"Accounts details: {len(accounts_details)}")
print(accounts_details.head(2))

# %%
# from the API as-is

slices = get_slices()
print(f"all slices: {len(slices)}")

persons = get_persons()
print(f"Persons: {len(persons)}")

events = get_events()
print(f"Events: {len(events)}")

# %%
# leases is a combination of the API data and the historical data

leases1 = load_old_leases()
leases2 = get_leases_df()
leases_df = pd.concat([leases1, leases2])
leases_df.sort_values(by='beg')
print(f"Leases: {len(leases_df)}")

# %%
# attach slices to persons using historical data

slice_persons = load_slice_persons(slices, events)
print(f"Slice persons: {len(slice_persons)}")


# %% [markdown]
# ## monitor progress

# %%
def summarize_persons(persons):
    c = Counter([p['family'] for p in persons])
    print(f"person families: {c}")
    print(f"total {len(persons)} persons / {c[None] + c['disabled']} unresolved")


# %%
def show_missing_persons(persons, show_disabled=True):
    missing_disabled = 0
    for person in persons:
        # resolved
        if person['family'] is not None:
            continue
        if not person['enabled'] and not show_disabled:
            missing_disabled += 1
            continue
        print(f"unresolved person (enabled={person['enabled']}): {person['email']}")
    if missing_disabled:
        print(f"skipped {missing_disabled} disabled persons")


# %%
def summarize_slices(slices):
    c = Counter([s['family'] for s in slices])
    print(f"slice families: {c}")
    print(f"total {len(slices)} slices / {c[None]} unresolved")


# %%
summarize_persons(persons)
summarize_slices(slices)


# %%
def summarize_and_check_leases(leases_df, slices):
    known_slices = {s['name'] for s in slices if s['family']}
    unresolved_leases = leases_df.loc[~ leases_df.name.isin(known_slices)]
    unresolved = len(unresolved_leases)
    print(f"leases: {len(leases_df)} / unresolved: {unresolved}")
    if unresolved != 0:
        print(f"We have {unresolved} unresolved leases !!")
        print(unresolved_leases.name.unique())
        raise RuntimeError("We have {unresolved} unresolved leases")


# %% [markdown]
# ## tag persons

# %%
def tag_persons(persons, accounts_details):
    for person in persons:
        if person['family'] is not None:
            continue
        try:
            family = accounts_details.loc[person['email'], 'family']
            if family:
                person['family'] = family
        except KeyError:
            pass


# %%
tag_persons(persons, accounts_details)
summarize_persons(persons)

# %%
show_missing_persons(persons, show_disabled=False)


# %% [markdown]
# ## tag slices
#
# code to fill-in the family tag for slices, if it's missing  
# this means that the information in the DB will "win" over all these heristics

# %% [markdown]
# ### as admin

# %%
def tag_admin_slices(slices):
    for slice in slices:
        if slice['family'] is not None:
            continue
        if is_admin_slice(slice['name']):
            slice['family'] = 'admin'


# %%
tag_admin_slices(slices)
summarize_slices(slices)


# %% [markdown]
# ### from the hard-wired list

# %%
def tag_slices_from_hard_wired_data(slices):
    for slice in slices:
        if slice['family'] is not None:
            continue
        if slice['name'] in SLICE_FAMILIES:
            slice['family'] = SLICE_FAMILIES[slice['name']]


# %%
tag_slices_from_hard_wired_data(slices)
summarize_slices(slices)


# %% [markdown]
# ### from slice_persons

# %%
def tag_slices_from_slice_persons(slices, persons, slice_persons):
    person_index = {person['person_id']: person for person in persons}
    for slice in slices:
        if slice['family'] is not None:
            continue
        slice_id = slice['slice_id']
        if slice_id not in slice_persons:
            continue
        # some persons may have been deleted
        persons = [person_index.get(person_id, None) for person_id in slice_persons[slice_id]]
        persons = [person for person in persons if person is not None]
        person_families = set(person['family'] for person in persons)
        family = relevant_family(person_families)
        print(f"slice {slice['name']} has {len(persons)} persons with families {person_families} -> {family}")
        slice['family'] = family


# %%
tag_slices_from_slice_persons(slices, persons, slice_persons)

# %%
summarize_slices(slices)

# %% [markdown]
# ## raincheck

# %%
summarize_and_check_leases(leases_df, slices)
print("we are good to go")

# %% [markdown]
# ## build the usage dataframe

# %% [markdown]
# ### raw data

# %%
# df = pd.DataFrame(leases).set_index('lease_id')
df = leases_df
df.head()
df.dtypes

# %%
df.head(2)

# %% [markdown]
# ### compute duration

# %%
# manage duration

df['duration'] = df['end'] - df['beg']
print(f"before cleanup: {len(df)} leases")
# somehow a few items in there have a negative duration
df.drop(df.loc[df.duration < pd.Timedelta(0)].index, inplace=True)
print(f"after cleanup: {len(df)} leases")

# %%
df.head(2)

# %% [markdown]
# ### add family to leases

# %%
# add a family column - i.e. join with slices

slice_family = {slice['name']: slice['family'] for slice in slices if slice['family']}
df['family'] = df['name'].apply(lambda name: slice_family[name])

# df.head()

# %%
# make family a category

df['family'] = df['family'].astype('category')

# %%
# remove future slices
df = df[df['beg'] < pd.Timestamp.now()]

# %%
df.describe()
# df.head()

# %%
df.family.value_counts()

# %%
df.info()

# %% [markdown]
# ### remove admin slices (or not)

# %%
# let's remove the admin slices as they are not representative

# print(f"we have a total of {len(df)} leases")
# df = df.loc[df.family != 'admin']
# print(f"we focus on a total of {len(df)} non-admin leases")

# %%
df.describe()

# %%
expected = ( (0, 0), (1, 1), (3600, 1), (3601, 2), (7199, 2), (7200, 2))


# %% [markdown]
# ### how to count hours
#
# we want to convert seconds into hours, rounded to ceiling

# %%
def round_timedelta_to_hours(timedelta):
    x = timedelta
    if isinstance(x, pd.Timedelta):
        x = timedelta.total_seconds()
    return int(((x-1) // 3600) + 1)


# %%
# test it
def test_round_timedelta_to_hours():
    for arg, exp in expected:
        got = round_timedelta_to_hours(arg)
        print(f"with {arg=} we get {got} and expect {exp} -> {got == exp}")
        arg = pd.Timedelta(seconds=arg)
        got = round_timedelta_to_hours(arg)
        print(f"with {arg=} we get {got} and expect {exp} -> {got == exp}")

# test_round_timedelta_to_hours()


# %% [markdown]
# ## plots

# %%
from IPython.display import display
import matplotlib.pyplot as plt

# %matplotlib ipympl

# %% [markdown]
# ### prepare the data

# %%
# groupby family and by period - do the sum of durations - convert in hours - return as a pivot

def prepare_plot_pivot(df, period):
    """
    period should be something like 'W' or 'M' or 'Y'
    """
    # create a column for the groupby thanks to to_period
    df['period'] = df.beg.dt.to_period(period)
    return (
        df.pivot_table(
            values='duration',
            index='period',
            columns='family',
            aggfunc='sum',
            observed=False,
        )
        .map(round_timedelta_to_hours)
    )


# %%
dfw = prepare_plot_pivot(df, 'W')
dfm = prepare_plot_pivot(df, 'M')
dfy = prepare_plot_pivot(df, 'Y')


# %% [markdown]
# ### per family per period

# %%
def draw(dfd, period):
    # plt.figure()
    ax = dfd.plot.bar(
        figsize=(12, 8),
        stacked=True,
        # won't work with bar plots
        # x_compat= True,
        # not that helpful
        # rot=45,
        title=f"Usage in total hours per family per {period}",
    )
    match period:
        case 'week':
            ax.set_xticks(range(0, len(dfd), 12))
        case 'month':
            ax.set_xticks(range(0, len(dfd), 3))
    plt.savefig(f"usage-{period}.png")
    plt.show()


# %%
# draw them all

for dfd, period in (dfw, 'week'), (dfm, 'month'), (dfy, 'year'):
# for dfd, period in (dfm, 'month'), (dfy, 'year'):
    draw(dfd, period)

# %% [markdown]
# ## summary per slice
#
# ### a usage table per slice and per family

# %%
slice_summary = df.pivot_table(
    values='duration',
    index='name',
    columns='family',
    aggfunc='sum',
    observed=False,
)
slice_summary.to_csv("slice-summary.csv")
slice_summary


# %% [markdown]
# ### a summary list of families per slice and per person

# %%
def list_current_families(current_list, readable_key, show_admin=False):
    for item in sorted(current_list, key=lambda x: x[readable_key]):
        if item['family'] is not None:
            if item['family'] == 'admin' and not show_admin:
                continue
            print(f"{item[readable_key]} -> {item['family']}")

list_current_families(slices, 'name')

# %%
list_current_families(persons, 'email')


# %% [markdown]
# ## upload new families
#
# this section is aimed as a one-shot operation to upload the new families to the PLCAPI
# once this is done, hopefully we can deal with new users and slices directly in the DB through PLEWWW that has a way to do that

# %%
def compare_and_upload_news(
        typename, readable_key, current_list, retriever_function,
        show_none=False, dry_run=True):
    """
    returns a list of dictionaries suitable for the PLC API function Update{typename}
    """
    id_key = f"{typename}_id"
    old_list = retriever_function()
    new_list = current_list
    print(f"original {typename} list: {len(old_list)}")
    print(f"new {typename} list: {len(new_list)}")
    # find the ones whose family has changed
    old_index = {item[id_key]: item for item in old_list}
    new_index = {item[id_key]: item for item in new_list}

    result = []
    count = 0
    count_override = 0
    for item in new_list:
        item_id = item[id_key]
        if item_id not in old_index:
            print(f"{typename} {item_id} just appeared")
        else:
            old_item = old_index[item_id]
            if item['family'] == old_item['family']:
                continue
            count += 1
            is_override = old_item['family'] is not None
            count_override += is_override
            message = "OVERRIDE !!" if is_override else ""
            record_it = True if not is_override else show_none
            print_it = True if is_override or show_none else False
            if record_it:
                result.append((item_id, {'family': item['family']}))
            if print_it:
                print(f"{message}{typename} {item_id} ({item[readable_key]}) has changed from None to {item['family']}")
    print(f"we have a total of {count} {typename}s that have changed family ({count_override} overriden)")
    return sorted(result, key=lambda x: x[0])


# %%
def apply_changes(changes, typename):
    """
    changes is a list of tuples (id, record)
    as returned by compare_and_upload_news
    """
    auth, proxy = init_proxy()
    methodname = f"Update{typename.capitalize()}"
    updater = proxy.__getattr__(methodname)
    for id, record in changes:
        print(f"updating {id}")
        try:
            updater(auth, id, record)
        except Exception as e:
            print(f"OOPS, could not update {typename} {id} - {type(e)} - {e}")


# %% [markdown]
# ### slices

# %%
slice_updates = compare_and_upload_news("slice", "name", slices, get_slices)
slice_updates[:5]

# %%
# [slice for slice in slices if slice['slice_id'] == 6]

# %%
apply_changes(slice_updates, "slice")

# %%
# compare_and_upload_news("person", "email", persons, get_persons)

# %% [markdown]
# ## sandbox
#
# this will get trashed eventually
