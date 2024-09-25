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
def get_leases():
    auth, proxy = init_proxy()
    return proxy.GetLeases(auth)

# %%
def get_events():
    auth, proxy = init_proxy()
    return proxy.GetEvents(auth, {'call_name': 'AddPersonToSlice'})


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
# ## other manual classification tools

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
        case 'inria_admin' | 'inria_r2lab.admin' | 'inria_r2lab.nightly':
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
# ### families
#
# when a slice has several families, we can manually tag it with the most relevant one

# %%
# pick the highest-ranking wmong this list

ORDERED_FAMILIES = [
    "unknown",
    "admin",
    "academia/diana",
    "academia/fit-slices",
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



# %%
TESTS = [
    {"admin", "academia/diana"},
    {"admin", "academia/fit-slices"},
    {"academia/fit-slices", "academia/others"},
    {"admin", "industry"},
    {"admin", "unknown"},
    {"ACADEMIA/diana", "academia/fit-slices"},
    {"ACADEMIAsdf/diana", "academia/fit-slices"},
    {"ACADEMIAsdf/diana"},
    {"academia/diana", "academia/others"},
    {"academia/diana", "industry"},
    {"academia/diana", "unknown"},
    {"academia/fit-slices", "academia/others"},
    {"academia/fit-slices", "industry"},
    {"academia/fit-slices", "unknown"},
    {"academia/others", "industry"},
    {"academia/others", "unknown"},
    {"industry", "unknown"},
    {"unknown", "unknown"},
    [],
]

def test_relevant_family():
    for test in TESTS:
        print(f"test {test} -> {relevant_family(test)}")

test_relevant_family()

# %% [markdown]
# ## actually load data

# %%
accounts_details = get_accounts_details()
print(f"Accounts details: {len(accounts_details)}")
print(accounts_details.head(2))

# %%
slices = get_slices()
print(f"all slices: {len(slices)}")

leases = get_leases()
leases.sort(key=lambda l: l['t_from'])
print(f"Leases: {len(leases)}")

persons = get_persons()
print(f"Persons: {len(persons)}")

events = get_events()
print(f"Events: {len(events)}")

# %%
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
    for person in persons:
        # unrsolved
        if person['family'] is None:
            if not person['enabled'] and not show_disabled:
                continue
            print(f"unresolved person (enabled={person['enabled']}): {person['email']}")


# %%
def summarize_slices(slices):
    c = Counter([s['family'] for s in slices])
    print(f"slice families: {c}")
    print(f"total {len(slices)} slices / {c[None]} unresolved")


# %%
summarize_persons(persons)
summarize_slices(slices)


# %%
def summarize_and_check_leases(leases, slices):
    known_slices = {s['slice_id'] for s in slices if s['family']}
    unresoved_leases = {
        lease for lease in leases if lease['slice_id'] not in known_slices
    }
    unresolved = len(unresoved_leases)
    print(f"leases: {len(leases)} / unresolved: {unresolved}")
    if unresolved != 0:
        raise RuntimeError("We have {unresolved} unresolved leases")



# %% [markdown]
# ## tag persons

# %% [markdown]
#

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
show_missing_persons(persons)


# %% [markdown]
# ## tag slices

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
summarize_and_check_leases(leases, slices)
print("we are good to go")

# %% [markdown]
# ## build the usage dataframe

# %% [markdown]
# ### raw data

# %%
df = pd.DataFrame(leases).set_index('lease_id')
df.head()

# %% [markdown]
# ### clean and type data

# %%
# discard non-needed columns

if 'node_type' in df.columns:
    df.drop(columns=['node_type', 'hostname', 'site_id', 'node_id', 'expired', 'duration'], inplace=True)
# df.head()

# %%
# manage dates

if 't_from' in df.columns:
    df['beg'] = pd.to_datetime(df['t_from'], unit='s')
    df['end'] = pd.to_datetime(df['t_until'], unit='s')
    df['duration'] = df['end'] - df['beg']
    df.drop(columns=['t_from', 't_until'], inplace=True)
# df.head()

# %%
# add a family column - i.e. join with slices

slice_family = {slice['slice_id']: slice['family'] for slice in slices if slice['family']}
df['family'] = df['slice_id'].apply(lambda slice_id: slice_family[slice_id])

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

# %%
# # let's remove the admin slices as they are not representative

# print(f"we have a total of {len(df)} leases")
# df = df.loc[df.family != 'admin']
# print(f"we focus on a total of {len(df)} non-admin leases")

# %%
df.describe()

# %% [markdown]
# ### how to count hours
#
# we want to convert seconds into hours, rounded to ceiling

# %%
expected = ( (0, 0), (1, 1), (3600, 1), (3601, 2), (7199, 2), (7200, 2))


# %%
def round_timedelta_to_hours(timedelta):
    x = timedelta
    if isinstance(x, pd.Timedelta):
        x = timedelta.seconds
    return int(((x-1) // 3600) + 1)


# %%
# test it

for arg, exp in expected:
    got = round_timedelta_to_hours(arg)
    print(f"with {arg=} we get {got} and expect {exp} -> {got == exp}")
    arg = pd.Timedelta(seconds=arg)
    got = round_timedelta_to_hours(arg)
    print(f"with {arg=} we get {got} and expect {exp} -> {got == exp}")

# %% [markdown]
# ## plots

# %%
from IPython.display import display
import matplotlib.pyplot as plt

# %matplotlib ipympl

# %% [markdown]
# ### per family per period

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
    plt.show()


# %%
# just one
draw(dfy, 'year')

# %%
# draw them all

for dfd, period in (dfw, 'week'), (dfm, 'month'), (dfy, 'year'):
    draw(dfd, period)

# %% [markdown]
# ## sandbox
#
# this will get trashed eventually

# %% [markdown]
# ### the sum does not add up
#
# tally by month is smaller than by week !

# %%
df.tail()

# %%
# a short extract: focus on 2024

dfs = df.loc[(df.beg.dt.year >= 2024) & (df.beg.dt.year <= 2024)].copy()
# dfs = df.loc[(df.beg.dt.year >= 2026)]
dfs.head(2)

# %%
dfs.tail(2)

# %%
# apply the same processing by month and week

sm = prepare_plot_pivot(dfs, 'M')
sw = prepare_plot_pivot(dfs, 'W')
# sd = prepare_plot_pivot(dfs, 'D')


# %%
# the first 4 weeks of 2024

sw.head(4)

# %%
# and the month view does not add up !

sm.head(2)

# %%
dfs1 = dfs.loc[(dfs.beg.dt.month <= 1)]
dfs1


# %%
# draw(sm, 'month')
# draw(sw, 'week')
# draw(sd, 'day')

# %% [markdown]
# ### GetLeases() misses the early leases
#
# some point in time circa march 2018, as part of some maintenance cleanup, the unique node has been renamed
# from `37nodes.r2lab.inria.fr` to `faraday.inria.fr`;
# at least that's my conjecture, because GetLeases() has data only from about that time
#
# so in this part we are doing some archeology in the Events database to recover the missing leases, and focus on the ones that were attached to the old nodename.

# %% [markdown]
#

# %%
# retrieve all the events 

auth, proxy = init_proxy()
lease_events = proxy.GetEvents(auth, {'call_name': 'AddLeases'})
df_lease_events = pd.DataFrame(lease_events)
len(df_leases_events)

# %%
# there are several formats for the dates
call1 = "AddLeases[{'AuthMethod': 'password', 'AuthString': 'Removed by API', 'Username': 'root@r2lab.inria.fr'}, ['37nodes.r2lab.inria.fr'], 'inria_oai.build', 1474542000, 1474556400]"
# or
call2 = "AddLeases[{'AuthMethod': 'password', 'AuthString': 'Removed by API', 'Username': 'root@r2lab.inria.fr'}, ['37nodes.r2lab.inria.fr'], 'inria_oai.build', '2016-12-19 14:00:00', '2016-12-19 15:00:00']"
# or
call3 = "AddLeases[{'AuthMethod': 'password', 'AuthString': 'Removed by API', 'Username': 'root@r2lab.inria.fr'}, [1], 'inria_r2lab.nightly', 1606615200, 1606618800]"

# turns out the last format has only been used for the nightly slice
# so we can just ignore it

# %%
import re

re_between_quotes = re.compile(r".*'([^']*)'.*")
re_int_in_brackets = re.compile(r".*\[(\d+)\].*")
re_digits_only = re.compile(r"(\d+)[^\d]*$")
re_date = re.compile(r"^[^\d]*(\d+-\d+-\d+)$")
re_time = re.compile(r"^(\d+:\d+:\d+)[^\d]*$")
format_date_time = "%Y-%m-%d %H:%M:%S"

def parse_call(call):
  try:
    *_, nodepart, slicepart, frompart, topart = call.split()
    if match := re_digits_only.match(topart):
        # FORMAT 1
        beg = pd.to_datetime(match.group(1), unit='s')
        end = pd.to_datetime(int(re_digits_only.match(frompart).group(1)), unit='s')
    else:
        *_, nodepart, slicepart, fromdate, fromtime, todate, totime = call.split()
        from_string = re_date.match(fromdate).group(1) + " " + re_time.match(fromtime).group(1)
        to_string = re_date.match(todate).group(1) + " " + re_time.match(totime).group(1)
        beg = pd.to_datetime(from_string, format=format_date_time)
        end = pd.to_datetime(to_string, format=format_date_time)
    slicename = re_between_quotes.match(slicepart).group(1)
    if match := re_between_quotes.match(nodepart):
        nodename = match.group(1)
    else:
        nodename = re_int_in_brackets.match(nodepart).group(1)

    return nodename, slicename, beg, end
  except Exception as e:
    print(f"OOPS: {e} with {call}")
    return None, None, None


# %%
# parse all calls

extra_leases1 = df_lease_events['call'].map(parse_call)

# %%
# transform into a proper dataframe

extra_leases2 = pd.DataFrame(extra_leases1.tolist(), columns=['node', 'slice', 'beg', 'end'])

# %%
# keep only the ones corresponding to the historical hostname

extra_leases3 = extra_leases2.loc[extra_leases2.node == '37nodes.r2lab.inria.fr']
len(extra_leases3)

# %%
extra_leases3.tail()


# %%
extra_leases2.node.unique()

# %%
