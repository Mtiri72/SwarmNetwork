# How to run the code:
1. make sure to have the hostnames set in the format: [some_name][some_number] for example: r1, r2, ... etc.
2. consult the ./lib/global_config.py and configure the physical ip of the node that is running the database, plus the physcial ips of the access points. marked in the file with TODO
3. start the cassandra database by executing the ```./run_cassandra_docker.sh``` and wait for the database to start.
4. to check the database execute the command ```docer exec -it cassandra bash``` and then inside the container run the command ```cqlsh``` to connect the CLI to the database, the database takes about a minute or two to start so be patient at this step. from the cqlsh cli run ```SELECT * FROM ks_swarm.active_nodes; ``` to see the swarm database.
5. source the script run.sh providing two arguments: first argument is the role of the node: [ap: for access point, sn: for smart node, co: for coordinator], second argument is the logging level, suggested to be 40 to show only errors, for more comprehensive debugging set it to 10 for debugging (slows the execution of the code) for example: ```source run.sh ap 40```
6. the wifi hotspot will be started at the access point and has the format R[some_number]AP
7. connect the smart nodes to the wifi, name is ```R[some_number]AP``` and password is ```123456123```
8. start the ros containers, they should be able to communicate.