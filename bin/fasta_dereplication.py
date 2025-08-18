#!/usr/bin/python
#
# Dereplicates fasta files using vsearch
#

import os
import subprocess
import argparse
import glob

from pathlib import Path


def find_files(directory,pattern):
    return glob.glob(os.path.join(directory,pattern))

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
            description="""Converts fastq files to fasta""")
    parser.add_argument(
            '--input_dir',
            dest='input_dir',
            required=True,
            help='Input directory containing fastq files')
    parser.add_argument(
            '--output_dir',
            dest='output_dir',
            required=True,
            help='Output directory to hold fasta files')
    args = parser.parse_args()

    fasta_files = find_files(args.input_dir, '*.fasta')

    for fasta in fasta_files:
        # Names will have _R_merged and we want to go back to the
        # sample name. So remove the _R_merged...
        #
        # NAR_BT_240701_1_S66_R_merged.fasta
        # ->
        # NAR_BT_240701_1_S66.fasta
        #
        new_fname = Path(fasta).name.replace("_R_merged", "")
        tag = Path(new_fname).stem
        out_fname = Path(args.output_dir) / new_fname
        try:
            print(f'vsearch --derep_fulllength={fasta} --sizeout --output={out_fname} --relable={tag}-')
            subprocess.check_output([
                'vsearch', 
                f'--derep_fulllength={fasta}',
                '--sizeout',
                f'--output={out_fname}',
                f'--relabel={tag}-'])
        except:
            print(f"ERROR: Failed to run vsearch dereplication for: {fasta}")
            bang
