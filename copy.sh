#!/bin/bash
#PBS -q copyq
#PBS -P qp00
#PBS -l ncpus=1,mem=4GB,walltime=10:00:00
#PBS -l storage=scratch/qp00+gdata/qp00
#PBS -j oe
cd /scratch/qp00/db9528/EOS26
rsync -a --size-only --no-inc-recursive --info=progress2 \
      EOS26_cache/ /g/data/qp00/db9528/EOS26_cache/ \
      > /g/data/qp00/db9528/rsync_EOS26_cache.log 2>&1

find EOS26_cache -type f | wc -l
find /g/data/qp00/db9528/EOS26_cache -type f | wc -l
