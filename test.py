import socket
with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.bind(('', 25565))
        # sock.setblocking(False)
        sock.settimeout(10)
        
        sock.sendto(b"Uism7Q,kill",("localhost", 37777))