from enum import Enum, auto
import json

class String_Constants(str, Enum):
    def __repr__(self):
        return self.name
    
    @classmethod
    def __iter__(cls):
        return iter(member.name for member in cls)
    
    
    VXLAN_ID = auto()
    VETH1_VIP = auto()
    VETH1_VMAC = auto()
    COORDINATOR_VIP = auto()
    COORDINATOR_TCP_PORT = auto()
    AP_ID = auto()
    AP_IP = auto()
    AP_MAC = auto()
    SWARM_ID = auto()
    JOIN_REQUEST = auto()

class Control_Message_Keys(str, Enum):
    def __repr__(self):
        return self.name
    
    def __str__(self):
        return self.name

    TYPE = auto()
    REQUIST_ID = auto()
    THIS_NODE_UUID = auto()
    THIS_NODE_APID = auto()
 
 
CMKs = Control_Message_Keys
STRs = String_Constants

for i in STRs:
    print(i)



join_request_dic = {
    CMKs.TYPE:           STRs.JOIN_REQUEST,
    CMKs.REQUIST_ID:     1,
    CMKs.THIS_NODE_UUID: 2,
    CMKs.THIS_NODE_APID: 3
}

print(json.dumps(join_request_dic))

exit()


data1 = {key.name: str(value) for key, value in join_request_dic.items()}

print(json.dumps(data1))

print(join_request_dic)

exit()

# data1 = {key.name: value for key, value in data.items()}

# data2 = {key.value: value for key, value in data.items()}

# json.dumps(data1)

# json.dumps(data2)

# print('data1: ', data1)

# print('--------')

# print('data2', data2)