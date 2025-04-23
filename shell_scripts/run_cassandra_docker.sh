if [ "$(sudo docker container inspect -f '{{.State.Status}}' 'cassandra' )" != "running" ]; then
    echo "Starting Cassandra Container"
    sudo docker run --rm -d --name cassandra --hostname cassandra --network host cassandra
else echo "Cassandra container is running"
fi