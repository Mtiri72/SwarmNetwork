#!/bin/bash
SCRIPT_PATH="${BASH_SOURCE[0]:-$0}";
cd "$( dirname -- "$SCRIPT_PATH"; )";

BMV2_IMAGE=se_network:v1
BMV2_CONTAINER=se_network

if [ "$(sudo docker container inspect -f '{{.State.Status}}' $BMV2_CONTAINER )" != "running" ]; then
    echo "Starting Container $BMV2_CONTAINER"
    sudo docker run --privileged --rm --net=host --volume $(pwd):$(pwd) --workdir $(pwd) -i -t --name $BMV2_CONTAINER -d $BMV2_IMAGE
fi
