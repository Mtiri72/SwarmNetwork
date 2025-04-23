#!/bin/bash

# This function prints the next IP
nextip(){
    IP=$1
    IP_HEX=$(printf '%.2X%.2X%.2X%.2X\n' `echo $IP | sed -e 's/\./ /g'`)

    NEXT_IP_HEX=$(printf %.8X `echo $(( 0x$IP_HEX + $2 + $3 ))`)
    NEXT_IP=$(printf '%d.%d.%d.%d\n' `echo $NEXT_IP_HEX | sed -r 's/(..)/0x\1 /g'`)
    echo "$NEXT_IP"
}

SUBNET1='10.0.0.0'
SUBNET2='192.168.137.0'
MASK1='/24'
MASK2='/24'
DEFAULT_GATEWAY='192.168.137.1'


HOST_NAME=$(cat /etc/hostname)
HOST_ID=$(echo "$HOST_NAME" | grep -oE '[0-9]+' | head -n 1)


IP1_ETH0=$(nextip $SUBNET1 $HOST_ID 0)
IP2_ETH0=$(nextip $SUBNET2 $HOST_ID 100)

ip address add ${IP1_ETH0}${MASK1} dev eth0
ip address add ${IP2_ETH0}${MASK2} dev eth0
ip link set eth0 up

ip route add default via $DEFAULT_GATEWAY

nmcli connection modify eth0 ipv4.dns "8.8.8.8 8.8.4.4"
nmcli connection up eth0



