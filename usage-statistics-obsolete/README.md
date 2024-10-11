
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

see https://github.com/fit-r2lab/r2lab.inria.fr/tree/main/stats

for more details on the new workflow
