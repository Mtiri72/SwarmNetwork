# This tells python to look for files in parent folders
import sys
# setting path
sys.path.append('.')
sys.path.append('..')
sys.path.append('../..')

import subprocess
import logging
import logging.handlers

import threading
import socket
import atexit
import time
import ipaddress
import lib.global_config as cfg
import psutil
import sys
import lib.database_comms as db
import lib.bmv2_thrift_lib as bmv2
import os
import asyncio
import lib.global_constants as cts
from lib.helper_functions import *
import json
import concurrent.futures

from argparse import ArgumentParser
from performance_timer import timeit, time_block, start_timer, stop_timer

STRs = cts.String_Constants

class SocketStreamHandler(logging.StreamHandler):
    """Custom StreamHandler to send logs over TCP."""
    def __init__(self, host, port):
        super().__init__(sys.stdout)  # StreamHandler needs an output stream
        self.host = host
        self.port = port
        self.sock = None
        self._connect()

    def _connect(self):
        """Establish connection to log server."""
        try:
            self.sock = socket.create_connection((self.host, self.port))
        except Exception as e:
            print(f"Failed to connect to log server: {e}")
            self.sock = None

    def emit(self, record):
        """Send log message to log server."""
        if not self.sock:
            self._connect()  # Try to reconnect if needed
            if not self.sock:
                return  # Drop log if connection fails

        try:
            msg = self.format(record) + "\n"
            self.sock.sendall(msg.encode('utf-8'))  # Send log as bytes
        except Exception as e:
            print(f"Error sending log: {e}")
            self.sock = None  # Reset socket on failure

    def close(self):
        """Close the socket when done."""
        if self.sock:
            self.sock.close()
        super().close()



parser = ArgumentParser()
parser.add_argument("-l", "--log-level",type=int, default=50, help="set logging level [10, 20, 30, 40, 50]")
parser.add_argument("-n", "--num-id",type=int, default=50, help="sequential uniq numeric id for node identification")
args = parser.parse_args()

dir_path = os.path.dirname(os.path.realpath(__file__))
loopback_if = 'lo:0'

THIS_AP_UUID = None
for snic in psutil.net_if_addrs()[loopback_if]:
    if snic.family == socket.AF_INET:        
        temp_mac = int_to_mac(int(ipaddress.ip_address(snic.address) -1 ))
        THIS_AP_UUID = f'AP:{temp_mac[9:]}'
if THIS_AP_UUID == None:
    exit()

# this part handles logging to console and to a file for debugging purposes
# where to store program logs
PROGRAM_LOG_FILE_NAME = './logs/ap.log'

os.makedirs(os.path.dirname(PROGRAM_LOG_FILE_NAME), exist_ok=True)
logger = logging.getLogger(f'{THIS_AP_UUID}')

log_socket_handler = SocketStreamHandler( cfg.logs_server_address[0], cfg.logs_server_address[1] )
log_info_formatter =  logging.Formatter("%(name)s %(asctime)s [%(levelname)s]:\n%(message)s\n")
log_socket_handler.setFormatter(log_info_formatter)
log_socket_handler.setLevel(logging.INFO)

client_monitor_log_console_handler = logging.StreamHandler(sys.stdout)
log_debug_formatter = logging.Formatter("Line:%(lineno)d at %(asctime)s [%(levelname)s] Thread: %(threadName)s File: %(filename)s :\n%(message)s\n")
client_monitor_log_console_handler.setFormatter(log_debug_formatter)
client_monitor_log_console_handler.setLevel(args.log_level)

logger.setLevel(logging.DEBUG)
logger.addHandler(log_socket_handler)
logger.addHandler(client_monitor_log_console_handler)

db.db_logger = logger
bmv2.bmv2_logger = logger



# a global variable to set the communication protocol with the switch
P4CTRL = bmv2.P4_CONTROL_METHOD_THRIFT_CLI

INDEX_IW_EVENT_MAC_ADDRESS = 3
INDEX_IW_EVENT_ACTION = 1 

IW_TOOL_JOINED_STATION_EVENT = 'new'
IW_TOOL_LEFT_STATION_EVENT = 'del'

# read the swarm subnet from the config file
# TODO: make this configurable by coordinator
THIS_SWARM_SUBNET=ipaddress.ip_address( cfg.this_swarm_subnet )

DEFAULT_SUBNET=ipaddress.ip_address(f'10.0.{args.num_id}.0')

COORDINATOR_S0_IP = f'10.0.{args.num_id}.254'

# a variable to track created host ids
# TODO: have a database table for this
# current_host_id = config.this_swarm_dhcp_start
created_vxlans = set([])


SWARM_P4_MC_NODE = 1100
SWARM_P4_MC_GROUP = 1000


# a list to keep track of connected stations to current AP
connected_stations = {}


CONNECTED_STATIONS_VMAC_INDEX = 0
CONNECTED_STATIONS_VIP_INDEX = 1
CONNECTED_STATION_VXLAN_INDEX = 2

DEFAULT_WLAN_DEVICE_NAME= cfg.default_wlan_device


db.DATABASE_IN_USE = db.STR_DATABASE_TYPE_CASSANDRA
database_session = db.connect_to_database(cfg.database_hostname, cfg.database_port)
db.DATABASE_SESSION = database_session

THIS_AP_ETH_MAC = None
for snic in psutil.net_if_addrs()[cfg.default_backbone_device]:
    if snic.family == psutil.AF_LINK:        
        THIS_AP_ETH_MAC = snic.address
if THIS_AP_ETH_MAC == None:
    logger.error("Could not Connect to backbone, check eth device name in the config file")
    exit()

THIS_AP_WLAN_MAC = None
for snic in psutil.net_if_addrs()[cfg.default_wlan_device]:
    if snic.family == psutil.AF_LINK:        
        THIS_AP_WLAN_MAC = snic.address
if THIS_AP_WLAN_MAC == None:
    logger.error("Could not Connect to backbone, check eth device name in the config file")
    exit()
                         
def initialize_program():    
    # remvoe all configureation from bmv2, start fresh
    bmv2.send_cli_command_to_bmv2(cli_command="reset_state")

    # attach the backbone interface to the bmv2
    bmv2.send_cli_command_to_bmv2(cli_command=f"port_remove {cfg.swarm_backbone_switch_port}")
    bmv2.send_cli_command_to_bmv2(cli_command=f"port_add {cfg.default_backbone_device} {cfg.swarm_backbone_switch_port}")
    
    coordinator_vmac = int_to_mac( int( ipaddress.ip_address(cfg.coordinator_vip)) )
    print(f'Coordinator MAC { coordinator_vmac}')
    entry_handle = bmv2.add_entry_to_bmv2(communication_protocol= bmv2.P4_CONTROL_METHOD_THRIFT_CLI,
                                            table_name='MyIngress.tb_ipv4_lpm',
    action_name='MyIngress.ac_ipv4_forward_mac', match_keys=f'{cfg.coordinator_vip}/32' , 
    action_params= f'{cfg.swarm_backbone_switch_port} { coordinator_vmac }')
    
    
    entry_handle = bmv2.add_entry_to_bmv2(communication_protocol= bmv2.P4_CONTROL_METHOD_THRIFT_CLI,
                                            table_name='MyIngress.tb_ipv4_lpm',
    action_name='MyIngress.ac_ipv4_forward_mac', match_keys=f'{COORDINATOR_S0_IP}/32' , 
    action_params= f'{cfg.swarm_backbone_switch_port} { coordinator_vmac }')
    
    # handle broadcast
    bmv2.send_cli_command_to_bmv2(cli_command=f"mc_mgrp_create {SWARM_P4_MC_GROUP}")
    bmv2.send_cli_command_to_bmv2(cli_command=f"mc_node_create {SWARM_P4_MC_NODE} {cfg.swarm_backbone_switch_port}")
    bmv2.send_cli_command_to_bmv2(cli_command=f"mc_node_associate {SWARM_P4_MC_GROUP} 0")
    bmv2.send_cli_command_to_bmv2(cli_command=f"table_add MyIngress.tb_l2_forward ac_l2_broadcast 01:00:00:00:00:00&&&0x010000000000 => {SWARM_P4_MC_GROUP} 100 ")
    
    logger.info(f"AP ID: {THIS_AP_UUID} is up" )
    print('\n\n\nAP Started')

# a handler to clean exit the programs
def exit_handler():
    log_socket_handler.close()
    pass


# a function for sending the configuration to the swarm node
# this connects to the TCP server running in the swarm node and sends the configuration as a string
@timeit
def send_swarmNode_config(config_messge, node_socket_server_address):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as node_socket_client:
        try:
            node_socket_client.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            node_socket_client.settimeout(10)
            node_socket_client.connect(node_socket_server_address)
            node_socket_client.sendall( bytes( config_messge.encode() ))
            response = node_socket_client.recv(1024).decode()
            if response == "OK!":
                return 1
            return -1 
        except Exception as e:
            logger.error(f'Error sending config to {node_socket_server_address}: {e}')
            return -1




@timeit
def create_vxlan_by_host_id(vxlan_id, remote, port=4789): 
    logger.debug(f'Adding se_vxlan{vxlan_id}')
    
    add_vxlan_shell_command = "ip link add se_vxlan%s type vxlan id %s dev %s remote %s dstport %s" % (
        vxlan_id, vxlan_id, DEFAULT_WLAN_DEVICE_NAME, remote, port)

    result = subprocess.run(add_vxlan_shell_command.split(), text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if (result.stderr):
        logger.error(f'\nCould not create se_vxlan{vxlan_id}:\n\t {result.stderr}')
        return -1
    
    logger.debug(f'\nCreated se_vxlan{vxlan_id}')
    created_vxlans.add(int(vxlan_id) )
    
    logger.debug(f'\nCreated_vxlans:\n\t {created_vxlans}')            
    activate_interface_shell_command = "ip link set se_vxlan%s up" % vxlan_id
    result = subprocess.run(activate_interface_shell_command.split(), text=True , stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if (result.stderr):
        logger.error(f'\nCould not activate interface se_vxlan{vxlan_id}:\n\t {result.stderr}')
        return -1
    logger.debug(f'\nActivated interface se_vxlan{vxlan_id}')
    return vxlan_id
        
@timeit
def delete_vxlan_by_host_id(host_id):
    logger.debug(f'\nDeleting se_vxlan{host_id}')
    delete_vxlan_shell_command = "ip link del se_vxlan%s" % (host_id)
    result = subprocess.run(delete_vxlan_shell_command.split(), text=True , stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if (result.stderr):
        logger.error(f'\ncould not delete se_vxlan{host_id}:\n\t {result.stderr}')
        return
    logger.debug(f'\nCreated Vxlans before removing {host_id}: {created_vxlans}')
    if int(host_id) in created_vxlans:
        created_vxlans.remove( int(host_id) )
        logger.debug(f'\nCreated Vxlans after removing {host_id}: {created_vxlans}')

@timeit
def get_mac_from_arp_by_physical_ip(ip):
    shell_command = "arp -en"
    result = subprocess.run( shell_command.split(), text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if (result.stderr):
        logger.error(f'\nCould run arp for {ip}:\n\t {result.stderr}')
        return

    for line in result.stdout.strip().splitlines():
        if ip in line:
            return line.split()[2]
    logger.error(f'\nMAC not found in ARP for {ip}')
    return None


@timeit
def get_ip_from_arp_by_physical_mac(physical_mac):
    shell_command = "arp -en"
    t0 = time.time()
    while time.time() - t0 < 5:
        result = subprocess.run( shell_command.split(), text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if (result.stderr):
            logger.error(f'\nCould not run arp for {physical_mac}:\n\t {result.stderr}')
            return
        for line in result.stdout.strip().splitlines():
            if physical_mac in line and DEFAULT_WLAN_DEVICE_NAME in line:
                ip = line.split()[0]
                logger.debug(f'\nIP {ip} was found in ARP for {physical_mac} after {time.time() - t0} Seconds')                
                return ip
 
@timeit
def get_next_available_vxlan_id():
    shell_command = "ip -d link show | awk '/vxlan id/ {print $3}' "
    process_ret = subprocess.run(shell_command, text=True, shell=True, stdout=subprocess.PIPE )
    id_list_str = process_ret.stdout
    id_list = list(map(int, id_list_str.split()))
    result = min(set(range(1, 500 )) - set(id_list)) 
    return result 


@timeit
async def handle_new_connected_station(station_physical_mac_address):
    logger.debug(f"handling newly connected staion {station_physical_mac_address}")

    if (station_physical_mac_address in connected_stations.keys()):
        logger.warning(f'\nStation {station_physical_mac_address} Connected to {THIS_AP_UUID} but was found already in Connected Stations')
        return

    with time_block("ARP Resolution"):
        station_physical_ip_address = get_ip_from_arp_by_physical_mac(station_physical_mac_address)
    if (station_physical_ip_address == None ):
        logger.error(f'\nIP not found in ARP for {station_physical_mac_address}. Aborting the handling of the node')
        return

    logger.info( f'\nNew Station Connected: {station_physical_mac_address} {station_physical_ip_address} at {time.ctime(time.time())}')

    SN_UUID = 'SN:' + station_physical_mac_address[9:]

    with time_block("ART DB Lookup"):
        node_db_result = db.get_node_info_from_art(node_uuid=SN_UUID)
        node_info = node_db_result.one()

    logger.debug(f'node_info: {node_info} for {SN_UUID}')

    if ( node_info == None or node_info.current_swarm == 0):
        logger.debug(f'Configuring Swarm 0 for {SN_UUID}')

        with time_block("VXLAN Check + Assignment"):
            command = f"ip -d link show | awk '/remote {station_physical_ip_address}/ {{print $3}}' "
            proc_ret = subprocess.run(command, shell=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if proc_ret.stderr:
                logger.error(f"Error running: {command}\nError Message:\n{proc_ret.stdout} ")
                logger.error(f"Something wrong with assigning vxlan to {SN_UUID} ")
                return

            vxlan_id = -1
            if (proc_ret.stdout == '' ):
                vxlan_id = get_next_available_vxlan_id()
            else:
                vxlan_id = int(proc_ret.stdout)
                command = f"ip link del se_vxlan{vxlan_id}"
                subprocess.run(command, shell=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if (vxlan_id == -1):
                logger.error(f"Something wrong with assigning vxlan to {SN_UUID} ")
                return

        with time_block("VXLAN Interface Creation"):
            create_vxlan_by_host_id( vxlan_id= vxlan_id, remote= station_physical_ip_address )

        with time_block("BMv2 Port Handling"):
            bmv2.send_cli_command_to_bmv2(cli_command=f"port_remove {vxlan_id}")
            bmv2.send_cli_command_to_bmv2(cli_command=f"port_add se_vxlan{vxlan_id} {vxlan_id}")

        with time_block("Virtual IP/MAC Assignment"):
            node_s0_ip = str(DEFAULT_SUBNET).split('.')[:3]
            node_s0_ip.append(station_physical_ip_address.split('.')[3])
            node_s0_ip = '.'.join(node_s0_ip)
            node_s0_mac = int_to_mac(int( ipaddress.ip_address(node_s0_ip) ))
            coordinator_vip = DEFAULT_SUBNET + 254

        with time_block("Send TCP Config to Node"):
            swarmNode_config = {
                STRs.TYPE.name: STRs.SET_CONFIG.name,
                STRs.VETH1_VIP.name: node_s0_ip,
                STRs.VETH1_VMAC.name: node_s0_mac,
                STRs.VXLAN_ID.name: vxlan_id,
                STRs.SWARM_ID.name: 0,
                STRs.COORDINATOR_VIP.name: str(coordinator_vip),
                STRs.COORDINATOR_TCP_PORT.name: cfg.coordinator_tcp_port,
                STRs.AP_UUID.name: THIS_AP_UUID
            }
            swarmNode_config_message = json.dumps(swarmNode_config)
            result = send_swarmNode_config(swarmNode_config_message, (station_physical_ip_address, cfg.node_manager_tcp_port))
            if (result == -1):
                logger.error(f'Smart Node {station_physical_ip_address} could not handle config:\n{json.dumps(swarmNode_config, indent = 2 ) }')
                return
            else:
                logger.info(f'AP has sent this config to the Smart Node:\n\t {json.dumps(swarmNode_config, indent = 2 )}')

        connected_stations[station_physical_mac_address] = [ station_physical_mac_address ,node_s0_ip, vxlan_id]

        with time_block("ART Insert"):
            db.insert_into_art(node_uuid=SN_UUID, current_ap=THIS_AP_UUID, swarm_id=0, ap_port=vxlan_id, node_ip=node_s0_ip)

        with time_block("Local & Remote P4 Setup"):
            entry_handle = bmv2.add_entry_to_bmv2(
                communication_protocol= bmv2.P4_CONTROL_METHOD_THRIFT_CLI,
                table_name='MyIngress.tb_ipv4_lpm',
                action_name='MyIngress.ac_ipv4_forward_mac_from_dst_ip',
                match_keys=f'{node_s0_ip}/32',
                action_params= f'{str(vxlan_id)}')

            node_ap_ip = cfg.ap_list[THIS_AP_UUID][0]
            ap_ip_for_mac_derivation = cfg.ap_list[THIS_AP_UUID][1]
            for key in cfg.ap_list.keys():
                if key != THIS_AP_UUID:
                    ap_ip = cfg.ap_list[key][0]
                    ap_mac = int_to_mac( int(ipaddress.ip_address(ap_ip_for_mac_derivation)) )
                    entry_handle = bmv2.add_entry_to_bmv2(
                        communication_protocol= bmv2.P4_CONTROL_METHOD_THRIFT_CLI,
                        table_name='MyIngress.tb_ipv4_lpm',
                        action_name='MyIngress.ac_ipv4_forward_mac',
                        match_keys=f'{node_s0_ip}/32',
                        action_params= f'{cfg.swarm_backbone_switch_port} {ap_mac}',
                        thrift_ip= ap_ip, thrift_port= bmv2.DEFAULT_THRIFT_PORT )

    else:
        logger.info(f'node {SN_UUID} is part of swarm {node_info.current_swarm}')

        with time_block("VXLAN Setup for Existing Node"):
            command = f"ip -d link show | awk '/remote {station_physical_ip_address}/ {{print $3}}' "
            proc_ret = subprocess.run(command, shell=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if proc_ret.stderr:
                logger.error(f"Error running: {command}\nError Message:\n{proc_ret.stdout} ")
                logger.error(f"Something wrong with assigning vxlan to {SN_UUID} ")
                return

            vxlan_id = -1
            if (proc_ret.stdout == '' ):
                vxlan_id = get_next_available_vxlan_id()
            else:
                vxlan_id = int(proc_ret.stdout)
                command = f"ip link del se_vxlan{vxlan_id}"
                subprocess.run(command, shell=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if (vxlan_id == -1):
                logger.error(f"Something wrong with assigning vxlan to {SN_UUID} ")
                return

        with time_block("VXLAN Creation & BMv2 Attach"):
            create_vxlan_by_host_id( vxlan_id= vxlan_id, remote= station_physical_ip_address )
            bmv2.send_cli_command_to_bmv2(cli_command=f"port_remove {vxlan_id}")
            bmv2.send_cli_command_to_bmv2(cli_command=f"port_add se_vxlan{vxlan_id} {vxlan_id}")

        with time_block("Virtual IP & MAC Assignment"):
            host_id = db.get_next_available_host_id_from_swarm_table(first_host_id=cfg.this_swarm_dhcp_start,
                        max_host_id=cfg.this_swarm_dhcp_end, uuid=SN_UUID)
            result = assign_virtual_mac_and_ip_by_host_id(subnet= THIS_SWARM_SUBNET, host_id=host_id)
            station_vmac= result[0]
            station_vip = result[1]

        with time_block("Send Config to Node"):
            swarmNode_config = {
                STRs.TYPE.name                  : STRs.UPDAET_CONFIG.name,
                STRs.VETH1_VIP.name             : station_vip,
                STRs.VETH1_VMAC.name            : station_vmac,
                STRs.VXLAN_ID.name              : vxlan_id,
                STRs.SWARM_ID.name              : node_info.current_swarm,
                STRs.COORDINATOR_VIP.name       : cfg.coordinator_vip,
                STRs.COORDINATOR_TCP_PORT.name  : cfg.coordinator_tcp_port,
                STRs.AP_UUID.name               : THIS_AP_UUID
            }
            swarmNode_config_message = json.dumps(swarmNode_config)
            result = send_swarmNode_config(swarmNode_config_message, (station_physical_ip_address, cfg.node_manager_tcp_port)  )
            if (result == -1):
                logger.error(f'Smart Node {station_physical_ip_address} could not handle config:\n{swarmNode_config_message}')
                return

        connected_stations[station_physical_mac_address] = [ station_physical_mac_address ,station_vip, vxlan_id]

        with time_block("DB & ART Insert"):
            db.insert_into_art(node_uuid=SN_UUID, current_ap=THIS_AP_UUID, swarm_id=node_info.current_swarm, ap_port=vxlan_id, node_ip=station_vip)
            db.insert_node_into_swarm_database(node_uuid=SN_UUID, this_ap_id= THIS_AP_UUID,
                                            host_id=host_id, node_vip=station_vip, node_vmac=station_vmac,
                                            node_phy_mac=station_physical_mac_address, status=db.db_defines.SWARM_STATUS.JOINED.value)

        with time_block("Remote Rule Insertions Loop"):
            for key in cfg.ap_list.keys():
                if key != THIS_AP_UUID:
                    label = f"Insert Remote Rule for {key}"
                    try:
                        with time_block(label):
                            ap_ip = cfg.ap_list[key][0]
                            ap_ip_for_mac_derivation = cfg.ap_list[key][1]
                            ap_mac = int_to_mac(int(ipaddress.ip_address(ap_ip_for_mac_derivation)))
                    
                            entry_handle = bmv2.add_entry_to_bmv2(
                                communication_protocol=bmv2.P4_CONTROL_METHOD_THRIFT_CLI,
                                table_name='MyIngress.tb_ipv4_lpm',
                                action_name='MyIngress.ac_ipv4_forward_mac',
                                match_keys=f'{station_vip}/32',
                                action_params=f'{cfg.swarm_backbone_switch_port} {ap_mac}',
                                thrift_ip=ap_ip,
                                thrift_port=bmv2.DEFAULT_THRIFT_PORT
                            )
                    except Exception as e:
                        logger.error(f"Failed to insert remote rule for {key}: {repr(e)}")






@timeit                    
async def handle_disconnected_station(station_physical_mac_address):
    try: 
        SN_UUID = 'SN:' + station_physical_mac_address[9:]

        with time_block("ART DB Lookup"):
            node_db_result = db.get_node_info_from_art(node_uuid=SN_UUID)
            node_info = node_db_result.one()
        node_ap = THIS_AP_UUID
        if node_info:
            node_ap = node_info.current_ap

        if station_physical_mac_address not in connected_stations.keys() or node_ap != THIS_AP_UUID:
            logger.warning(f'\nStation {station_physical_mac_address} disconnected from AP but was not found in connected stations')
            return

        with time_block("Disconnection Confirmation Wait"):
            t0 = time.time()
            while time.time() - t0 < cfg.ap_wait_time_for_disconnected_station_in_seconds:
                cli_command = "iw wlan0 station dump | grep Station | awk '{print $2}'"
                proc_res = subprocess.run(cli_command, shell=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                if proc_res.stderr:
                    logger.error(f"Error running command: {cli_command}\nError Message: {proc_res.stderr}")
                if station_physical_mac_address in proc_res.stdout:
                    return

                cli_command = f"ping -c 1 {get_ip_from_arp_by_physical_mac(station_physical_mac_address)}"
                proc_res = subprocess.run(cli_command.split(), shell=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                time.sleep(1)

        with time_block("ART DB Lookup 2nd Pass"):
            node_db_result = db.get_node_info_from_art(node_uuid=SN_UUID)
            node_info = node_db_result.one()

        if node_info is None or node_info.current_ap != THIS_AP_UUID:
            with time_block("Remove BMv2 Port (early exit)"):
                bmv2.remove_bmv2_swarm_broadcast_port(ap_ip='0.0.0.0', thrift_port=9090, switch_port=node_info.ap_port)
                try:
                    logger.debug(f"Connected Stations List before removing {station_physical_mac_address}: {connected_stations}")                
                    del connected_stations[station_physical_mac_address]
                    logger.debug(f"Connected Stations List after removing {station_physical_mac_address}: {connected_stations}")
                except:
                    logger.error(f'could not delete station from connected station set {repr(e)}')
            return

        logger.info(f'Removing disconnected Node: {station_physical_mac_address}')
        logger.debug(f"Connected Stations List before removing {station_physical_mac_address}: {connected_stations}")                

        with time_block("Extract Station Metadata"):
            station_virtual_ip_address = connected_stations[station_physical_mac_address][CONNECTED_STATIONS_VIP_INDEX]
            station_virtual_mac_address = connected_stations[station_physical_mac_address][CONNECTED_STATIONS_VMAC_INDEX]
            station_vxlan_id = connected_stations[station_physical_mac_address][CONNECTED_STATION_VXLAN_INDEX]

        with time_block("Delete from Connected Station List"):
            del connected_stations[station_physical_mac_address]
            logger.debug(f"Connected Stations List after removing {station_physical_mac_address}: {connected_stations}")

        #with time_block("Delete P4 Forwarding Entries from all APs"):
        #    for key in cfg.ap_list.keys():
        #        ap_ip = cfg.ap_list[key][0]
        #        logger.debug(f'deleting entries from: {key} with IP {ap_ip}')
        #        bmv2.delete_forwarding_entry_from_bmv2(
        #            communication_protocol=bmv2.P4_CONTROL_METHOD_THRIFT_CLI, 
        #            table_name='MyIngress.tb_ipv4_lpm',
        #            key=f'{station_virtual_ip_address}/32',
        #            thrift_ip=ap_ip,
        #            thrift_port=bmv2.DEFAULT_THRIFT_PORT
        #        )
        with time_block("Delete P4 Forwarding Entries from all APs"):
            for key in cfg.ap_list.keys():
                ap_ip = cfg.ap_list[key][0]
                label = f"Delete P4 Rule from {key}"
                with time_block(label):
                    logger.debug(f'deleting entries from: {key} with IP {ap_ip}')
                    bmv2.delete_forwarding_entry_from_bmv2(
                        communication_protocol=bmv2.P4_CONTROL_METHOD_THRIFT_CLI, 
                        table_name='MyIngress.tb_ipv4_lpm',
                        key=f'{station_virtual_ip_address}/32',
                        thrift_ip=ap_ip,
                        thrift_port=bmv2.DEFAULT_THRIFT_PORT
                    )

        with time_block("Remove BMv2 Port"):
            bmv2.remove_bmv2_swarm_broadcast_port(ap_ip='0.0.0.0', thrift_port=9090, switch_port=node_info.ap_port)
            delete_vxlan_from_bmv2_command = f"port_remove {station_vxlan_id}"
            bmv2.send_cli_command_to_bmv2(delete_vxlan_from_bmv2_command)

        with time_block("Delete Node from ART"):
            db.delete_node_from_art(uuid=SN_UUID)

        logger.info(f'station: {station_virtual_ip_address} left {THIS_AP_UUID}')

        with time_block("Delete VXLAN Interface"):
            delete_vxlan_by_host_id(station_vxlan_id)

    except Exception as e:
        logger.error(f"Error handling disconnected station {SN_UUID}: {repr(e)}")




def monitor_stations():
    # this command is run in the shell to monitor wireless events using the iw tool
    monitoring_command = 'iw event'

    # python runs the shell command and monitors the output in the terminal
    process = subprocess.Popen( monitoring_command.split() , stdout=subprocess.PIPE)
    previous_line = ''
    # we iterate over the output lines to read the event and react accordingly
    for output_line in iter(lambda: process.stdout.readline().decode("utf-8"), ""):
        if (output_line.strip() == previous_line.strip()):
            continue
        previous_line = output_line
        output_line_as_word_array = output_line.split()
        logger.debug( 'WiFi Event: ' + output_line )
        
        if output_line_as_word_array[INDEX_IW_EVENT_ACTION] == IW_TOOL_JOINED_STATION_EVENT:
            station_physical_mac_address = output_line_as_word_array[INDEX_IW_EVENT_MAC_ADDRESS]
            logger.debug( 'New Station MAC: ' + station_physical_mac_address )
            
            asyncio.run( handle_new_connected_station(station_physical_mac_address=station_physical_mac_address) )

        elif output_line_as_word_array[INDEX_IW_EVENT_ACTION] ==   IW_TOOL_LEFT_STATION_EVENT:
            station_physical_mac_address = output_line_as_word_array[INDEX_IW_EVENT_MAC_ADDRESS]
            logger.info( 'Disconnected Station MAC: ' + station_physical_mac_address )
            asyncio.run(  handle_disconnected_station(station_physical_mac_address=station_physical_mac_address) )


@timeit
def ap_id_to_vxlan_id(access_point_id):
    vxlan_id = cfg.vxlan_ids[access_point_id]
    return vxlan_id

        
def main():
    print("AP Starting")
    initialize_program()
    monitor_stations()
    
    # thread for monitoring connected devices to the AP WiFi network
    # monitor_stations_on_thread = threading.Thread(target=monitor_stations, args=()).start()
    

            
    
if __name__ == '__main__':
    atexit.register(exit_handler)
    main()
    
