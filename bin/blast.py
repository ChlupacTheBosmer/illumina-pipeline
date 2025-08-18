#!/usr/bin/python
# -*- coding: utf-8 -*-

import os
import shutil
import glob
import argparse
import subprocess
from pathlib import Path


def script_dir():
    return os.path.dirname(os.path.realpath(__file__))

def create_dir(path):
    try:
        os.makedirs(path)
    except:
        pass

def blast(project_dir, primer):
    home = os.path.expanduser("~")

    cluster_dir = '%s/clustered' % project_dir
    blast_dir = '%s/blasted' % project_dir

    results_file = '%s/results-%s.txt' % (cluster_dir, primer)

    blast_script = 'blast-%s' % primer
    blast_script_fname = '%s.sh' % blast_script
    blast_path_name = '%s/pipeline_scripts/%s' % (project_dir, blast_script_fname)

    clusterd_file = 'clustered-%s-multis' % primer
    clusterd_path = '%s/%s.fasta' % (cluster_dir, clusterd_file)

    create_dir(blast_dir)

    with open(blast_path_name, 'w') as sl:
        sl.write("#!/bin/bash\n")
        sl.write("touch %s_running\n" % blast_script)

        sl.write("# Code to run the procedure\n")
        sl.write('echo "Running BLAST on clustered file"\n')

        blast_csv = '%s/blast-%s.csv' % (blast_dir, clusterd_file)
        blast_log = '%s/blast-log-%s.txt' % (blast_dir, clusterd_file)
      
        blast_ref = '/data/genbank/2025-07-13/nt'

        if Path(f'{project_dir}/blast-ref').exists():
            blast_ref = Path(f'{project_dir}/blast-ref') / primer / primer

        sl.write(f"blastn -query '{clusterd_path}' -db '{blast_ref}' -out '{blast_csv}' -outfmt '10 std score qcovs stitle' -max_target_seqs 20 -num_threads 16 >& {blast_log}\n")

        # Process the BLAST results
        blast_summary = '%s/blast-summary-%s.csv' % (blast_dir, clusterd_file)
        sl.write("python %s/vsearch-blast-summary.py --blastinput=%s --otuinput=%s --outsummary=%s\n" %
                 (script_dir(), blast_csv, results_file, blast_summary))

        # Cur header from the top
        blast_summary_without_header = '%s.wh' % blast_summary
        sl.write("sed -e '1,1d' < %s > %s\n" % (blast_summary, blast_summary_without_header))
        sl.write('mv -f %s %s\n' % (blast_summary_without_header, blast_summary)) 

        # Process blast summary for manual excel checking
        sl.write('python %s/process_vsearch_blast_output_for_excel.py --csv=%s --project_dir=%s\n' %
                    (script_dir(), blast_summary, project_dir)) 

        # Sort the file in to largest first to smallest
        #blast_summary_sorted = '%s/blast-sorted-%s.csv' % (blast_dir, clusterd_file)
        #sl.write("sort -t $',' -k 2 -r -g -o %s %s\n" %
        #         (blast_summary_sorted, blast_summary))

        sl.write('mv %s_running %s_done\n' % (blast_script, blast_script))

        subprocess.run(['chmod', '+x', blast_path_name]) 


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
            description="""BLASTS dereplicated data""")
    parser.add_argument(
            '--project_dir',
            dest='project_dir',
            required=True,
            help='Project directory')
    parser.add_argument(
            '--primer',
            dest='primer',
            required=True,
            help='Primer name')

    args = parser.parse_args()
    blast(args.project_dir, args.primer)
