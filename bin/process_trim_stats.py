#!/usr/bin/python

import argparse
import os

from pathlib import Path

# Function to find n'th instance in a string
def findnth(haystack, needle, n):
    parts= haystack.split(needle, n+1)
    if len(parts)<=n+1:
        return -1
    return len(haystack)-len(parts[-1])-len(needle)

# Should be called with the trim file
parser = argparse.ArgumentParser(description='Creates summary of trim statistics')
parser.add_argument(
        '--trimfile', 
        help='Trim output file to process',
        type=str,
        required=True)
args = parser.parse_args()

# Test if the file exists.
trim_output = Path(args.trimfile)

if not trim_output.exists():
    print(f"ERROR: Trim output files doesent exist: {trim_output}")

outfile = trim_output.parent / 'trim_stats.csv'

# Open the csv file
with open(outfile,'w') as fd:
    fd.write('Sample,Reads,Both,Forward,Reverse,Dropped\n')

    # Work our way through the file. 
    # First look for the name of the processed pair and then the status
    with open(trim_output, "r") as tf:
        for line in tf:
            parts = line.split()
            if len(parts) == 0:
                continue
            # Look for the filename
            if parts[0] == '-threads':
                if len(parts) > 3:
                    fname_path = Path(parts[3])
                    fname = fname_path.name
                    sample_name = fname.split("_R")[0]
            # Look for the stats
            if parts[0] == 'Input':
                reads = parts[3]
                both = parts[6]
                forwards = parts[11]
                reverse = parts[16]
                dropped = parts[19]
                fd.write('%s,%s,%s,%s,%s,%s\n' %(sample_name,reads,both,forwards,reverse,dropped))

