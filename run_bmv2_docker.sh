#!/bin/bash
# if [ "$(sudo docker container inspect -f '{{.State.Status}}' 'bmv2smartedge' )" = "running" ]; then
#     echo "Stopping container bmv2smartedge"
#     sudo docker stop bmv2smartedge
#     sleep 1
# fi

echo "Starting Container bmv2smartedge"
sudo docker run --privileged --rm --net=host --volume $(pwd):$(pwd) --workdir $(pwd) -i -t --name bmv2smartedge -d bmv2se
sudo docker exec -d bmv2smartedge  pip install thrift
if [[ $1 != 'co' ]]; then
    echo -e "AP bmv2"
    sudo docker exec -d bmv2smartedge  simple_switch ./p4app/ap.json
fi