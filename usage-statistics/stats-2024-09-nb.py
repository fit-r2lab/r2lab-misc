# -*- coding: utf-8 -*-
# ---
# jupyter:
#   jupytext:
#     text_representation:
#       extension: .py
#       format_name: light
#   kernelspec:
#     display_name: Python 3 (ipykernel)
#     language: python
#     name: python3
#   language_info:
#     name: python
#     nbconvert_exporter: python
#     pygments_lexer: ipython3
# ---

# # Stats in R2lab

# ### convenience

# This cell is only here so that any change in the code gets reloaded.

# %load_ext autoreload
# %autoreload 2

# ## requirements

# First off, this is a jupytext-encoded notebook, you need to have jupytext installed to read it
#
#     pip install jupytext

# We use pandas
#
#     pip3 install pandas

# We also need an extra library to be able to read `xlsx` files directly:
#
#     pip3 install openpyxl

# ## workflow
#
# ### (TP)
# * gather all-slices (json) data on r2labapi (TP)
# * add resulting json to repo
#
# ### (WD) 
# * pull repo to get latest JSON
# * copy this notebook into a new one that reflects current month
# * run this notebook (WD)
#   * change name of reference json file
#   * follow the notebook, enter dates that cover time since last stats
#   * from that, we will compute the set of new accounts since last statistics (see OOPS's)
#   * which will need to be documented in the excel file `accounts-annotations.xlsx`
# * manually edit excell file, save and add to repo
# * re-run the notebook to produce whichever stats that you need

# ## scope
#
# The working assumption here is that the interesting data is
#
# * the percentage of usage over a given period `[start .. end]`
#
# * the total number of relevant accounts and slices
#
# * also we might wish to pinpoint entries in the db that
#   correspond to some operation conditions. For example,
#   as of march 2018, we are interested in the disabled accounts
#   attached to the r2lab site, because we suspect some people in
#   this set have been trying to join but that was never acted upon...

# ## changelog
#
# * 2019 April; issuing regular stsatistics
#
# * 2018 October; using this to prepare the stats exposed in the FIT meeting on Oct. 16
#
# * 2018 March; this is a rebuild - see `stats-old.py` - of a previously, rather *ad hoc* script. 
#   The present version will be OK for mostly 2017 and later, as we ignore the old data stored in json files.
#
# * 2017 November; at that time - again, see `stats-old.py` - we used 2 different sources of data, presumably because of the migration from the omf/rest API to myplc.

# ## prerequisite
#
# <div style="border: 3px dotted; text-align: center; background-color:red"><b>IMPORTANT !!</b> Walid you need to read this !</div>
#
# * we need to have the complete list of slices, but PLCAPI won't let us access to slices that are deleted - so essentially the ones that have expired;
#
# * so in order to compensate for that, we need to run the script `gather-slices.py` on `r2labapi.inria.fr` and then retrieve the corresponding output here - typically a file named `SLICES-2018-03-23.json`
#
# * this is to be performed by Thierry P. before anything else
#
# ```
# [root@r2labapi ~]# cd r2lab-misc/usage-statistics/
# [root@r2labapi usage-statistics]# git pull
# Updating 17c7136..d892b36
# Fast-forward
#  usage-statistics/gather-slices.py    | 73 +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#  usage-statistics/stats-2018-03.ipynb | 39 +++++++++++++++++++++++++++++++++------
#  2 files changed, 106 insertions(+), 6 deletions(-)
#  create mode 100755 usage-statistics/gather-slices.py
# [root@r2labapi usage-statistics]# ./gather-slices.py
# (Over)wrote SLICES-2018-03-23.json
# ```

# Then make sure to retrieve that file locally and define its name here:
#
# ```
# tparment ~/git/r2lab-misc/usage-statistics (master=) $ rsync -ai $(plr r2labapi):r2lab-misc/usage-statistics/SLICES\* .
# >f..t.... SLICES-2018-03-23.json
# ```

slices_filename = "SLICES-2024-09-23.json"

# +
import json

with open(slices_filename) as feed:
    all_slices = json.loads(feed.read())
    print("SLICES files loaded OK")
# -

# # proxying / password to the API

# You need to know the password of the PLCAPI admin account on `r2labapi.inria.fr`

# only prompt once so the notebook can be re-run often
import getpass
account = "root@r2lab.inria.fr"
try:
    if password:
        print("We know the password")
    else:
        raise ValueError
except:
    password = getpass.getpass(f"Enter password for {account} : ")

# +
# let's check that
auth = {'AuthMethod' : 'password',
        'Username'   : account,
        'AuthString' : password}

import xmlrpc.client
url = "https://r2labapi.inria.fr:443/PLCAPI/"
# -

proxy = xmlrpc.client.ServerProxy(url)
try:
    print("Authorization OK" if proxy.AuthCheck(auth)==1 else "KO")
except Exception as e:
    print(f"OOPS, something wrong with {type(e)} - {e}")

# *********

# ## enter your period of interest

# Enter your period of interest; this won't be prompted again if you re-run the cell, unless you comment off the `reset_period()` thingy (but turn it back off afterwards)

from timeutils import show_period, human_readable, reset_period, year_month_day

# +
# if you need to pick another scope, 
# uncomment and run the following line
# reset_period()

show_period();
# -

# # fetching user accounts

# +
all_accounts = proxy.GetPersons(auth)
all_accounts.sort(key=lambda account: account['date_created'])

print(f"We have {len(all_accounts)} accounts in the DB")

# FYI
enabled_accounts = proxy.GetPersons(auth, {'enabled': True})
enabled_accounts.sort(key=lambda account: account['date_created'])

print(f"FYI: We have {len(enabled_accounts)} enabled accounts in the DB")
# -

#
#

# +
# accessory

# This will add a `login_base` field to each user account
# to identify the attached institution:

all_sites = proxy.GetSites(auth)
site_hash = { site['site_id'] : site for site in all_sites}
for account in all_accounts:
    site_ids = account['site_ids']
    if not site_ids:
        account['login_base'] = '(none)'
    if len(site_ids) == 1:
        account['login_base'] = site_hash[account['site_ids'][0]]['login_base']
    else:
        account['login_base'] = '(' + ",".join(site_hash[site_id]['login_base'] for site_id in site_ids) + ')'
# -

# # classifications - import data from excel

# Let's load Walid's paper on the accounts; this is to be able to classify usages and accounts into several categories.

import pandas as pd

# +
# read excel file
# 02/2021 : encoding seems to have gone from the API, but seems no longer needed
#df = pd.read_excel('accounts-annotations.xlsx', encoding='cp1252')

df = pd.read_excel('accounts-annotations.xlsx', index_col='email')

# +
# visual check on a small sample
#df.iloc[3:6]
#df.dtypes
# -

# ### annotate `all_accounts` (and spot missing ones)
#
# this very basic loop just marks all rows with annotations;  
# it does a minimal check about the consistency of the xls file

# +
disabled = []
missing = []

for account in all_accounts:
    if not account['enabled']:
        disabled.append(account)
        continue
    try:
        email = account['email']
        excel_row = df.loc[email]
        # academia or industry
        family = excel_row['family']
        if not isinstance(family, str):
            # print(f"family type", type(family))
            family = ""
        if family.lower() in ('academia', 'industry'):
            account['family'] = family
        else:
            print(f"Unknown family `{family}` for {email} ! (in {account['login_base']})")
            account['family'] = 'unknown'
        if excel_row['diana'] == 'yes':
            account['scope'] = 'diana'
        elif excel_row['fit'] == 'yes':
            account['scope'] = 'fit'
        elif excel_row['others'] == 'yes':
            account['scope'] = 'others'
        else:
            print(f"Unknown scope for {email} ! (in {account['login_base']})")
            account['scope'] = 'unknown'
    except KeyError as exc:
        missing.append(account)

##############################
missing.sort(key=lambda account: account['date_created'])

print(
    f"we have {len(disabled)} disabled accounts\n"
    f"{len(missing)} true accounts that need being added into excel")
print(20*'-')    
for missing_account in missing:
    print(f"{year_month_day(missing_account['date_created'])} {missing_account['email']}")


# -

# If the above cell has not printed any warning, we have all active user accounts tagged with 
# * `family` as either `academia` or industry
# * `scope` as `diana`, `fit` or `others`

# # stats on user accounts

# +
# just a helper function that we'll user later on 

def show_accounts(accounts):
    accounts.sort(key = lambda person: person['date_created'])
    for i, account in enumerate(accounts, 1):
        default = 'n/a' if account['enabled'] else '--'
        print(f"[{i:02d}] "
              f" {'OK' if account['enabled'] else 'KO'}"
              f" {human_readable(account['date_created'])}"
              f" {account['login_base']:22s}",
              f" {account.get('family', default):8s}",
              f" {account.get('scope', default):8s}",
              f" {account['email']}")


# -

# ### narrowing on the selected period

ifrom, iuntil = show_period()
selected_accounts = [
    account for account in all_accounts 
    if account['date_created'] >= ifrom and
       account['date_created'] <= iuntil
]

# show_accounts(selected_accounts)
print(f"a total of {len(selected_accounts)} accounts were created over the selected period")

# ### focusing on enabled accounts (what really matters)

enabled_accounts_in_selected_period = [
    account for account in selected_accounts if account['enabled']
]

print(f"New enabled accounts in the selected period = {len(enabled_accounts_in_selected_period)}")

show_accounts(enabled_accounts_in_selected_period)

# ### by scope : diana / fit / others

# <div style="background-color: red; padding: 10px;">
# All the new people needs to be properly defined and marked in the excel file before we can proceed.
#     
# Check this: next cell should not print anything
# </div>    

# +
# let's check the excel file is complete
# should not find any account here !

for account in enabled_accounts_in_selected_period:
    if 'scope' not in account:
        print(f"account {account['email']} still not defined in excel")
# -

for scope in ['diana', 'fit', 'others']:
    scope_accounts = [account for account in enabled_accounts_in_selected_period
                       if account['scope'] == scope]
    print(f"in scope {scope}, {len(scope_accounts)} new enabled accounts")

# ### by family : academia / industry

for family in ['academia', 'industry', 'unknown']:
    family_accounts = [account for account in enabled_accounts_in_selected_period
                       if account['family'] == family]
    print(f"in family {family}, {len(family_accounts)} new enabled accounts")

# ### by perspective: aca⋇diana, aca⋇fit, aca*other, indus⋇other

# +
from itertools import product

all_perspectives = list(product(
    ('academia', 'industry', 'unknown'),
    ('diana', 'fit', 'others', 'unknown'),
))

perspectives = []
# this set is not enough when we get to tag slices as opposed to accounts
#    ('academia', 'diana'),
#    ('academia', 'fit'),
#    ('academia', 'others'),
#    ('industry', 'others'),


for family, scope in all_perspectives:
    perspective_accounts = [
        account for account in enabled_accounts_in_selected_period
        if account['family'] == family and
        account['scope'] == scope]
    if perspective_accounts:
        print(f"in perspective {family}⋇{scope}, {len(perspective_accounts)} new enabled accounts")
        perspectives.append((family, scope))
# -

# # classifying slices

# +
# sort in expiration order    
all_slices.sort(key = lambda slice: slice['expires'])
    
print(f"found {len(all_slices)} slices")    


# -

def show_slices(slices):
    for i, slice in enumerate(slices, 1):
        print(f"{i:02d} "
            f" created {human_readable(slice['created'])}"
            f" expires {human_readable(slice['expires'])}"
            f" {slice['name']}"
         )


# +
# show_slices(all_slices)
# -

# ### Ignoring admin slices

# +
admin_slices = ['auto_', 'nightly', 'maintenance', 'wa8il8im88fe' ]

def relevant(slice_or_lease):
    return not any(admin in slice_or_lease['name'] for admin in admin_slices)


# -

# ### classifying slices

# +
# create hashing index to quickly retrive an account by its person_id
accounts_hash = {account['person_id'] : account for account in all_accounts}

# mark all slice entry with a 'families' ans 'scopes' mark
# that gathers what is inherited from its accounts
for slice in all_slices:
    if not relevant(slice):
        continue
    person_ids = slice['person_ids']
    slice['families'] = [accounts_hash[person_id].get('family', '???')
                         for person_id in slice['person_ids']]
    slice['scopes'] = [accounts_hash[person_id].get('scope', '???')
                       for person_id in slice['person_ids']]
# -

# This is where we tag slices wrt family and scope; the decisions in here are **admittedly a little arbitrary**...

# +
# actually classify a slice in term of its
# family
# scope
# perspective
relevant_slices = []

verbose = False

def show_slices_classified():
    for slice in all_slices:
        if not relevant(slice):
            continue
        relevant_slices.append(slice)
        # tag slice 'family': consider a slice as industry if at least one account is industry
        slice['family'] = 'industry' if 'industry' in slice['families'] else 'academia'
        # tag slice 'scope': diana if all members are diana
        if all(map(lambda person_id: accounts_hash[person_id]['scope']=='diana', slice['person_ids'])):
            slice['scope'] = 'diana'
        elif all(map(lambda person_id: accounts_hash[person_id]['scope']=='fit', slice['person_ids'])):
            slice['scope'] = 'fit'
        else:
            slice['scope'] = 'others'
        print(f"slice {slice['name']} is tagged as {slice['family']}⋇{slice['scope']}",
              f"with {len(slice['person_ids'])} people", end="")
        if verbose:
              print(f"\n\t => {list(zip(slice['families'], slice['scopes']))}", end="")
        print()

show_slices_classified()


# +
print(f"we have a total of {len(relevant_slices)} relevant slices")
    
for family, scope in perspectives:
    in_perspective = [slice for slice in relevant_slices if slice['family'] == family and slice['scope'] == scope]
    print(f"{family}⋇{scope} -> {len(in_perspective)} slices")
# -

# # fetching leases

# +
# fetch leases for that period
selected_leases = proxy.GetLeases(
    auth,
    {'>t_from' : ifrom, '<t_from' : iuntil}
)

# Sort then in ascending order
selected_leases.sort(key=lambda lease: lease['t_from'])

print(f"there have been {len(selected_leases)} reservations made during the period")


# -

# ### a glimpse

# +
def lease_line(lease):
    return f"{lease['name']:25s} {human_readable(lease['t_from'])} -> {human_readable(lease['t_until'])}"

def glimpse(leases, size=5):
    for lease in leases[:size]:
        print(lease_line(lease))
    print("...")
    for lease in leases[-size:]:
        print(lease_line(lease))


# + cell_style="center"
glimpse(selected_leases)
# -

# # usage ratio

# ##### raw ratio *vs* opening hours
#
# The raw ratio is obtained by comparing the amount of time reserved with the total amount of time available.
#
# Assuming that opening hours would be mon-fri from 09:00 to 19:00

# +
# this is a constant

open_correction = (5 * 10) / (7 * 24)
print(f"CONSTANT: opening hours are {open_correction:.2%} of total hours")
# -

# ##### user *vs* admin
#
# We try to classify the various slices in 2 families whether they are for management/operations purposes, or used for actual experimentation.

total_duration = iuntil - ifrom


# +
# again this is a helper function 

def show_usage_ratio(leases, total_duration, message):

    def duration(lease):
        return lease['t_until'] - lease['t_from']

    reserved_duration = sum(duration(lease) for lease in leases)
    print(f"Total time reserved: {reserved_duration} / {total_duration:1.0f} s")
    print(f"                i.e: {reserved_duration/3600:.2f} / {total_duration/3600:.2f}    hours")
    print(f"                i.e: {reserved_duration/(24*3600):.2f} / {total_duration/(24*3600):.2f}       days")
    
    raw_ratio = reserved_duration / total_duration
    print(f"{message}: raw_ratio is {raw_ratio:.2%}")
    
    open_ratio = raw_ratio / open_correction
    print(f"{message}: open_ratio is {open_ratio:.2%}")


# + cell_style="center"
show_usage_ratio(selected_leases, total_duration, "ALL LEASES")
# -

# ### usage ratio - filtered

# We discard slices that have been run for administrative / operational purposes

filtered_leases = [lease for lease in selected_leases if relevant(lease)]

show_usage_ratio(filtered_leases, total_duration, "USER LEASES")

# ### classifying usage

# index to quickly retrieve slices
slice_index = {slice['slice_id']: slice for slice in all_slices}

for family, scope in perspectives:
    perspective_leases = []
    for lease in filtered_leases:
        slice = slice_index[lease['slice_id']]
        if slice['family'] != family or slice['scope'] != scope:
            continue
        perspective_leases.append(lease)
    print(20*'*', f"{family}⋇{scope} ==>", len(perspective_leases))
    if perspective_leases:
        show_usage_ratio(perspective_leases, total_duration, f"{family}⋇{scope}")

# these numbers are too rough; there is a need for some human correction to expose more meaningful numbers

# ### human estimation

# <div style="border: 3px dotted; text-align: center; background-color:red"><b>IMPORTANT !!</b></div>
#
#

# This method does not allow to conclude; this is due to the accounts / slice data model that does not allow to capture a meaningful classification mechanism.
#
# So, based on these results, and on what we've seen about the usage of the platform, we have made a human estimation to classify relevant (i.e. non administrative) usage as being
#
# * **total usage** ratio compared with **open hours**: 30%
# * out of which:
#     * **35%** diana
#     * **55%** academia
#     * **10%** industrial
#

# # accounts

# ### validated *vs* non-validated accounts
#
# Still on the selected period, show the ones that were enabled or not

enabled_selected_accounts = [ account for account in selected_accounts if account['enabled']]
disabled_selected_accounts = [ account for account in selected_accounts if not account['enabled']]

show_accounts(enabled_selected_accounts)

show_accounts(disabled_selected_accounts)
