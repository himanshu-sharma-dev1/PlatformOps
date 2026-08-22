#!/bin/bash

sudo apt-get install nfs-kernel-server
sleep 5
echo "/shared 192.168.0.10(rw,sync) 192.168.0.20(rw,sync)" >> /etc/exports


#/path/to/shared/folder machine1(options) machine2(options) ...

##/shared 192.168.0.10(rw,sync) 192.168.0.20(rw,sync)

sleep 5
sudo systemctl restart nfs-kernel-server