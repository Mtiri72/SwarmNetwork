#!/bin/bash

image_filename="se_network.tar"
expected_md5="4b0180a9b94289d097610ce43655d9e8"

if [ -f "$image_filename" ]; then
    echo "$image_filename found in current directory, skipping ..."
    exit
fi

echo "$image_filename was not found in current directory, fetching ..."
wget -O $image_filename https://tinyurl.com/54ntajmw

echo "Calculating MD5 checkSum for file $image_filename ..."
calculated_md5=$(md5sum se_network.tar | awk '{print $1}')
if [ "$calculated_md5" = "$expected_md5" ]; then
    echo "All good, MD5 hash matches"
else
    echo "Error: Attention! MD5 hash does NOT match the expected value"
fi



