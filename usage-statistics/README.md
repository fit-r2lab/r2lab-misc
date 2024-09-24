
# R2lab statistics

## history: before 2024 september

here's the workflow we had in place before september 2024

- an excel file named `accounts-annotations.xlsx` was kept in the git repo and managed manually
- it allowed to classify accounts in several categories, namely
  - academia or industry
  - and for academia, we had 3 subfamilies diana, fit and others
- plus we had a notebook template used to create a snapshot  
  (the `stats*.ipynb` files at first, then `stats*.py`)  
  that would produce the stats
- and this notebook relied on data gathered on the testbed and stored in files named `SLICES*.json`

### the caveats

having the annotations kept locally in this repo turned out to be a bad idea, as
it was no maintained over time, and so every time it was a struggle to get the
missing information

## the new workflow

### more flexible

- the Python code has been redesigned to be more flexibly invoked on a
  collection of periods, like e.g. gathering stats on a yearly basis

### accounts information

- we now have a dedicated shared google spreadsheet to store the annotations
- its format has been simplified to just 3 columns
  - email
  - year & month of registration
  - category
  - plus an optional comment; for instance this could contain elements provided
    by the user at registration time

#### HOWTO register a new user

- we receive a request from the website
- we reply directly and ask for a rationale; this is to make sure the user is
  not a bot, and to get more insights about the planned usage

### usage acquisition

unchanged for now:

- need to run `gather-slices.py` on `r2labapi.inria.fr`
- make sure to create a symlink `SLICES.json` to the latest file
