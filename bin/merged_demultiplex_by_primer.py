#!/usr/bin/python
# -*- coding: utf-8 -*-
###############################################################################
# Should be run in the directory that you want to process, could be run in the
# top level directory or in the directory you want to extract from.
#
# Note that this script works on the merged fastq files.
# To run me place me in the fastq directory along with the demux.slrum file.
# Edit the slrum file to use the directory path and then submit it with sbatch
# this should then run the demux on the fastqs in the directory.
###############################################################################

from Bio import SeqIO
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
import glob
import os
import fnmatch
import errno
import gzip
import re
import argparse


#forward_primers_full = {
#    'rbcLaF': 'ATGTCACCACAAACAGAGACTAAAGC',
#    'ITS2F': 'ATGCGATACTTGGTGTGAAT',
#}

minimum_seq_lengths = {
    'rbcL': 450,
    'ITS2': 300,
}

start_primers = {
    'rbcL': 'ACAGAGACTAAAGC',
    'ITS2': 'ACTTGGTGTGAAT',
}

end_primers = {
    'rbcL': 'TGAACAAGTATGG',
    'ITS2': 'G[A|C|T]GACC[C|T]CA[A|G][A|G]',
}

#reverse_primers_full = {
#    'rbcLr506': 'AGGGGACGACCATACTTGTTCA',
#    'ITS3R': 'GACGCTTCTCCAGACTACAAT',
#    'uniplantR': 'CCCG[A|C|T][C|T]TGA[C|T][C|T]TG[A|G]GGTC[A|G|T]C',
#}


def compressed_fastq_to_fasta(fastq_path):
    path, fname = os.path.split(fastq_path)
    fasta_path = os.path.join(path, '%s.fasta' % fname.split('.')[0])
    with gzip.open(fastq_path, "rt") as handle:
        with open(fasta_path, 'wt') as fasta_fh:
            SeqIO.write(
                sequences=list(SeqIO.parse(handle, "fastq")),
                handle=fasta_fh,
                format="fasta")


def fastq_gz_files(start_dir='.'):
    return sorted(Path(start_dir).glob("*.fastq.gz"))


def mkdirs():
    try:
        os.makedirs('unknown')
        os.makedirs('unknown/fastq')
    except OSError as e:
        if e.errno != errno.EEXIST:
            raise
    for primer in start_primers:
        try:
            os.makedirs(primer)
            os.makedirs('%s/fastq' % primer)
        except OSError as e:
            if e.errno != errno.EEXIST:
                raise


def demux(fname):
    metrics = {}

    try:
        with gzip.open(fname, "rt") as handle:
            metrics['filename'] = fname
            metrics['sequences'] = 0
            metrics['seq'] = {}
            
            for primer in list(start_primers.keys()) + ['unknown']:
                metrics['seq'][primer] = {
                    "file": gzip.open(
                        f'./{primer}/fastq/{os.path.basename(fname)}', "wt"),
                    "numof": 0}

            for rseq in SeqIO.parse(handle, "fastq"):
                metrics['sequences'] += 1
                found = False
                # Look for forward primer
                for primer in start_primers:
                    bcode = start_primers[primer]
                    if re.search(bcode, str(rseq.seq)[:50]):
                        SeqIO.write(
                            sequences=rseq,
                            handle=metrics['seq'][primer]['file'],
                            format="fastq")
                        metrics['seq'][primer]["numof"] += 1
                        found = True
                if not found:
                    # Didn't find so look for reverse primer
                    for primer in end_primers:
                        bcode = end_primers[primer]
                        if re.search(bcode, str(rseq.seq)[-50:]):
                            SeqIO.write(
                                sequences=rseq,
                                handle=metrics['seq'][primer]['file'],
                                format="fastq")
                            metrics['seq'][primer]["numof"] += 1
                            found = True
                    if not found:
                        SeqIO.write(
                            sequences=rseq,
                            handle=metrics['seq']['unknown']['file'],
                            format="fastq")
                        metrics['seq']['unknown']["numof"] += 1
    finally:
        for primer in list(start_primers.keys()) + ['unknown']:
            metrics['seq'][primer]['file'].close()
            metrics['seq'][primer]['file'] = ''

    return metrics


def demultiplex(fastq_files):
    with open('demultiplex_meta_data.csv', 'w') as md:
        header = 'Filename,Sequences,rbcL,ITS2,unknown\n'
        md.write(header)
        max_workers = os.cpu_count() or 1
        with ProcessPoolExecutor(max_workers=max_workers) as ex:
            future_map = {ex.submit(demux, p): p for p in fastq_files}
            complete = 0 
            for fut in as_completed(future_map):
                src = future_map[fut]
                try:
                    meta = fut.result()
                    complete += 1
                    print(
                        f'Done: {complete:03}, '  
                        f'{meta["filename"]}, '
                        f'{meta["sequences"]}, '
                        f'{meta["seq"]["rbcL"]["numof"]}, '
                        f'{meta["seq"]["ITS2"]["numof"]}, '
                        f'{meta["seq"]["unknown"]["numof"]}')
                    out = str('%s,%d,%d,%d,%d\n' % (
                        meta['filename'],
                        meta['sequences'],
                        meta['seq']['rbcL']['numof'],
                        meta['seq']['ITS2']['numof'],
                        meta['seq']['unknown']['numof']))
                    md.write(out)
                except Exception as x:
                    print(src.name, f'ERROR: {x}')


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
            description="""Reads the paired-merged files for rbcL and ITS2 sequences and demultiplexes them""")
    parser.add_argument(
            '--merge_dir',
            dest='input_dir',
            required=True,
            help='paired-merged directory')
    parser.add_argument(
            '--output_dir',
            dest='output_dir',
            required=True,
            help='Output directory')
    args = parser.parse_args()

    print(args)
    olddir = os.getcwd()
    os.chdir(args.output_dir)
    mkdirs()
    fastq_files = fastq_gz_files(args.input_dir)
    demultiplex(fastq_files)
    os.chdir(olddir)
