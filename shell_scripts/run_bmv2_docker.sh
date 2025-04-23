#!/bin/bash
SCRIPT_PATH="${BASH_SOURCE[0]:-$0}";
cd "$( dirname -- "$SCRIPT_PATH"; )/..";

BMV2_IMAGE=bmv2se
BMV2_CONTAINER=bmv2smartedge

if [ "$(sudo docker container inspect -f '{{.State.Status}}' $BMV2_CONTAINER )" != "running" ]; then
    echo "Starting Container $BMV2_CONTAINER"
    sudo docker run --privileged --rm --net=host --volume $(pwd):$(pwd) --workdir $(pwd) -i -t --name $BMV2_CONTAINER -d $BMV2_IMAGE
    sleep 5
    sudo docker exec -d bmv2smartedge  pip install thrift
    if [[ $1 != 'co' ]]; then
        echo -e "AP bmv2"
        sudo docker exec -d $BMV2_CONTAINER /bin/bash ./p4app/compile.sh
        sleep 3
        sudo docker exec -d $BMV2_CONTAINER simple_switch ./p4app/ap.json
    fi
fi
