#!/bin/bash

# This script will rsync data from remote server to research drive

sudo mount -t cifs -o username=clo36@ad.wisc.edu //research.drive.wisc.edu/kscranmer /mnt/research

sudo rsync -av --no-times --ignore-existing clo36@bear-dev:/home/clo36/
hf/hub/datasets--bigcode--the-stack-dedup /mnt/research/clo36/pelican-data-loader/data/datasets--bigcode
--the-stack-dedup/