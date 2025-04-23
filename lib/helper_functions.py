import json
import re



def enum_dictionary_to_json_string(dic_obj):
    return json.dumps({key.value: value for key, value in dic_obj.items()})


def int_to_mac(macint):
    if type(macint) != int:
        raise ValueError('invalid integer')
    return ':'.join(['{}{}'.format(a, b)
                     for a, b
                     in zip(*[iter('{:012x}'.format(macint ))]*2)])  # + 2199023255552
    
    

def assign_virtual_mac_and_ip_by_host_id( subnet, host_id):
    station_virtual_ip_address = str( subnet + host_id )
    station_virtual_mac_address = int_to_mac(int( subnet + host_id ))
       
    return station_virtual_mac_address, station_virtual_ip_address


def extract_numbers(lst):
    """
    Extracts numbers from a list of strings using regular expressions.
    """
    # Compile a regular expression pattern to match digits
    pattern = re.compile(r'\d+')
     
    # Use the pattern to extract all digits from each string in the list
    extracted_numbers = [pattern.findall(s) for s in lst]
     
    # Convert the extracted numbers from strings to integers
    return [int(x) for sublist in extracted_numbers for x in sublist]