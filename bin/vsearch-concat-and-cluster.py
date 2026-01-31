#!/usr/bin/python
# -*- coding: utf-8 -*-

import os
import shutil
import glob
import argparse
import subprocess

from pathlib import Path


def find_files(directory,pattern):
    return glob.glob(os.path.join(directory,pattern))


def create_dir(path):
    try:
        os.makedirs(path)
    except:
        pass


def concat_files(fname, files):
    with open(fname,'wb') as wfd:
        for f in files:
            with open(f,'rb') as fd:
                shutil.copyfileobj(fd, wfd, 1024*1024*10)


def cluster(project_dir, input_dir):
    fasta_fnames = find_files(input_dir, '*.fasta')
    bin_dir = Path(__file__).resolve().parent
    cluster_dir = os.path.abspath('%s/clustered' % project_dir)
    primer = os.path.basename(os.path.split(input_dir)[0])
    clustered_fname = '%s/clustered-%s.fasta' % (cluster_dir, primer)
    concat_file = '%s/concatenated-%s.fasta' % (cluster_dir, primer)
    results_file = '%s/results-%s.txt' % (cluster_dir, primer)
    vsearch_script = 'vsearch-%s' % primer
    vsearch_script_fname = '%s.sh' % vsearch_script
    vsearch_script_name = '%s/pipeline_scripts/%s' % (project_dir, vsearch_script_fname)

    create_dir(cluster_dir)

    pipeline_scripts_dir = os.path.dirname(vsearch_script_name)
    running_file_path = os.path.join(pipeline_scripts_dir, "%s_running" % vsearch_script)
    done_file_path = os.path.join(pipeline_scripts_dir, "%s_done" % vsearch_script)

    with open(vsearch_script_name, 'w') as sl:
        sl.write("#!/bin/bash\n")
        sl.write("touch %s\n" % running_file_path)

        sl.write("# Code to run the procedure\n")
        sl.write('echo "Running vsearch on the dereplicated fasta files"\n')

        sl.write('cat ')
        for fname in fasta_fnames:
            sl.write('%s ' % fname)
        sl.write(' > %s\n' % concat_file)

        sl.write('vsearch --cluster_size=%s --sizein --sizeout --uc=%s --id=1.0 --consout=%s\n' 
                 % (concat_file,results_file,clustered_fname))

        sl.write('%s/splitting_concat_clustered_file.py --input_file=%s\n' 
                % (bin_dir, clustered_fname))

        sl.write('mv %s %s\n' % (running_file_path, done_file_path))
    
    subprocess.run(['chmod', '+x', vsearch_script_name]) 


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
            description="""Concatenates and clusters dereplicated files""")
    parser.add_argument(
            '--input_dir',
            dest='input_dir',
            required=True,
            help='Input directory containing dereplicated fasta files')
    parser.add_argument(
            '--project_dir',
            dest='project_dir',
            required=True,
            help='Project directory')

    args = parser.parse_args()
    cluster(args.project_dir, args.input_dir)
