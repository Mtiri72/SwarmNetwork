# This is the global config file, all variables can be configured from here

# these are the L3 port numbers on which the databases listen
REDIS_PORT = 6379
CASSANDRA_PORT = 9042

# This is the number of the bmv2 port that is attached to the backbone network
# the backbone network is the network that connects the APs to the coordinator
swarm_backbone_switch_port = 510

## This is the interface at which the traffic is forwarded between the APs and the coordinator
## we created an overlay network as attaching the eth0 directly to bmv2 leads to performance degredation
## due to the high amount of background traffic genereted from the university network
default_backbone_device = 'smartedge-bb'
default_wlan_device = 'wlan0'


logs_server_address = ('192.168.137.106', 5000)

ap_wait_time_for_disconnected_station_in_seconds=5

# here configure the subnet range that need to be allocated to the swarm
# here we assume a /24 subnet mask
this_swarm_subnet='10.1.0.0'      ## this is the subnet to use for the swarm
this_swarm_subnet_mask='/24'
this_swarm_dhcp_start = 1         # this is the first IP to be assigned to the swarm node e.g: 10.0.1.1
this_swarm_dhcp_end  = 253        # last IP to be assigned e.g: 10.0.1.253, we leave the last IP for the coordinator


# default_subnet= "10.0.3.0"
# default_subnet_ap4= "10.0.4.0"

backbone_subnet='192.168.100.0'  #smartedge-bb
backbone_subnetmask='/24'

## This is the IP of the database, in my implementation the DB is running on the same node as the coordinator
## It uses the physical IP of the eth0 interface of the coordinator for consistency, and ease of routing

#TODO: configure this ip, physical IP where the database is running
database_hostname = '192.168.137.106'
database_port = CASSANDRA_PORT

# this IP is used to reach the coordinator by the swarm nodes
# this IP is also configured on the smartedge-bb interface of the coordinator
# it is sent to the swarm node when it connects to the AP

coordinator_vip='10.1.255.254'        # swarm virtual ip
coordinator_phyip='192.168.100.254' # physical ip of device 

# this is a tcp port number used to reach the coordinator from the swarm nodes
coordinator_tcp_port = 29997

# this is a tcp port number used to reach the swarm node manager from the access points
# in order to send the swarm config
node_manager_tcp_port = 29997


# list of access points in the network, used to propagate configuration changes
# this list of IPs are the ones configured on the smartedge-bb on each access point
# it is a different subnet from the one used by the swarm

#TODO: Configure this IP list, physical IPs of access points
ap_list = {
    # ID of AP        IP of eth0         IP smartedge-bb
    #'AP:00:00:03':  ['192.168.137.103', '192.168.100.3'],
    #'AP:00:00:04':  ['192.168.137.104', '192.168.100.4'],
    'AP:00:00:01':  ['192.168.137.105', '192.168.100.5']
    #'AP:00:00:07':  ['192.168.137.107', '192.168.100.7']  
    }

## currently unused
SWARM_P4_MC_NODE = 1100
SWARM_P4_MC_GROUP = 1000

