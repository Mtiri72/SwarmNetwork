import logging
import logging.handlers
import socketserver
import socket
import sys
import threading




# class MyTCPServer(socketserver.TCPServer):
#     def server_bind(self):
#         self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) # Example: reuse address
#         # Add other socket options here
#         super().server_bind() # Call the original server_bind()


# class LogHandler(socketserver.StreamRequestHandler):
#     """Handles incoming log records from clients."""
#     def handle(self):
#         logger = logging.getLogger("CentralLogger")
#         logger.addHandler(logging.StreamHandler(sys.stdout))
#         while True:
#             try:
#                 record = self.rfile.readline().strip()
#                 if not record:
#                     break
#                 print(record.decode('utf-8'))
#                 logger.info(record.decode('utf-8'))  # Decode and log the message
#             except Exception as e:
#                 print(f"Error handling log: {e}")
#                 break

# def start_log_server(host='0.0.0.0', port=5000):
#     """Starts the central log server."""
#     logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s\n\n')
#     server = MyTCPServer((host, port), LogHandler)
#     print(f"[*] Log server started on {host}:{port}")
#     server.serve_forever()

# if __name__ == "__main__":
#     start_log_server()





def handle_client(client_socket, address):
    try:
        while True:
            data = client_socket.recv(1500)  # Receive data (max 1024 bytes)
            if not data:
                break  # Exit loop if no data received (client disconnected)

            message = data.decode('utf-8')
            print(f"{message}")

    except Exception as e:
        print(f"Error handling client {address}: {e}")
    
    finally:
        print(f"[*] Closing connection from {address}")
        client_socket.close()  # Close client socket

def start_server(host="0.0.0.0", port=5000):
    """Starts a multi-client TCP server."""
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)  # TCP socket
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  # Allow reusing address
    server.bind((host, port))
    server.listen(10)  # Listen for up to 5 clients

    print(f"[*] Server listening on {host}:{port}")

    while True:
        client_socket, client_address = server.accept()  # Accept new connection
        client_thread = threading.Thread(target=handle_client, args=(client_socket, client_address))
        client_thread.start()  # Handle client in a new thread

if __name__ == "__main__":
    start_server()