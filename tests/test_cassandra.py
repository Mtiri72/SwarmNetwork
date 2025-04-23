# This tells python to look for files in parent folders
import sys
# setting path
sys.path.append('..')
sys.path.append('../..')

import lib.db.cassandra_db as cassandra_db
import lib.database_comms as db
import logging
logger = logging.getLogger('ap_logger')
logger = logging.getLogger('ap_logger')
client_monitor_log_formatter = logging.Formatter("\n\nLine:%(lineno)d at %(asctime)s [%(levelname)s]:\n\t %(message)s \n\n")
client_monitor_log_console_handler = logging.StreamHandler(sys.stdout)
client_monitor_log_console_handler.setLevel(logging.DEBUG)
client_monitor_log_console_handler.setFormatter(client_monitor_log_formatter)
logger.setLevel(logging.DEBUG)    

logger.addHandler(client_monitor_log_console_handler)
db.db_logger = logger



def connect_to_database(host, port):
        # CONNECT TO THE DATABASE
        cluster = cassandra_db.Cluster(
            contact_points=[host], 
                        port=port, 
                        load_balancing_policy=cassandra_db.DCAwareRoundRobinPolicy(local_dc='datacenter1'),
                        protocol_version=5
        )
        session = cluster.connect()
        return session

print('\n\n\n')
database_session = connect_to_database('0.0.0.0', 9042)


db.DATABASE_IN_USE = db.STR_DATABASE_TYPE_CASSANDRA
db.DATABASE_SESSION = database_session

