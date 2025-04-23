import socket



with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as node_socket_client:
    node_socket_client.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    node_socket_client.settimeout(10)
    try:
        node_socket_client.connect(('10.42.0.11', 29997 ))
        node_socket_client.sendall( bytes( 'HI'.encode() ))
        response = node_socket_client.recv(1024).decode()
    except Exception as e:
        print(e)
