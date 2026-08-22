#!/bin/bash

apt-get install nfs-common
sleep 5
mount 192.168.0.10:/shared /mnt