import socket
import configparser
import threading
import socket
import os
import time
import subprocess
import signal

class SharedResource:
    def __init__(self):
        self.files = []
        self.completed_files = []
        self.node_addresses = []
        self.lock = threading.Lock()
        self.connected=False
        self.server_addr=None

class VideoTransferNode:
    def __init__(self, host,shared_resource,transfer_recv_port,watch_folder,fin_folder):
        self.shared_resource= shared_resource
        self.watch_folder = watch_folder
        self.fin_folder = fin_folder
        self.host = host
        self.receive_port = transfer_recv_port
        self.running = True
        self.buffer_size = 4096

        self.receive_thread = threading.Thread(target=self.receive_video_files)
        self.send_thread = threading.Thread(target=self.send_video_files_to_server)
        self.process_thread = threading.Thread(target=self.process_video_file)
        self.process_thread.start()
        self.receive_thread.start()
        self.send_thread.start()


    def receive_video_files(self):
       client_socket, addr = None, None
       with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(('', self.receive_port))
            sock.listen(1)
            sock.settimeout(1)
            print(f"Node is listening for files on port {self.receive_port}")

            while self.running:
                try:
                    # if not self.shared_resource.connected:
                    client_socket, addr = sock.accept()
                    print(f"Connection from {addr}")
                    received = client_socket.recv(self.buffer_size).decode()
                    print(received)
                    filename, filesize = received.split('|')
                    filename = os.path.basename(filename)  # Ensure file is saved in the specified directory
                    filesize = int(filesize)
                    print(filesize)
                    client_socket.sendall(b'recv')

                    ffmpeg_options = client_socket.recv(self.buffer_size).decode("ascii")
                    client_socket.sendall(b'recv')

                    burnSubtitles = client_socket.recv(self.buffer_size).decode("ascii")
                    client_socket.sendall(b'recv')

                    with open(os.path.join(self.watch_folder, filename), 'wb') as f:
                        while filesize > 0:
                            bytes_read = client_socket.recv(self.buffer_size)
                            if not bytes_read:
                                break
                            f.write(bytes_read)
                            filesize -= len(bytes_read)
                        with self.shared_resource.lock:
                            self.shared_resource.files.append([filename,ffmpeg_options,burnSubtitles])

                    print(f"Received file {filename}. Added to queue.")
                    
                    # Check if the connection should be closed
                    if not self.shared_resource.connected:
                        print(f"Closing connection with {addr}")
                        client_socket.close()
                        
                except socket.timeout:
                    continue

    def send_video_files_to_server(self):
        while self.running:
            if self.shared_resource.completed_files:
                try:
                    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                        filename = self.shared_resource.completed_files[0][1]
                        sock.connect((self.shared_resource.server_addr[0], self.shared_resource.server_addr[2]))
                        old_filename=self.shared_resource.completed_files[0][0]
                        filepath = os.path.join(os.getcwd(),self.fin_folder,filename)
                        filesize = os.path.getsize(filepath)

                        sock.sendall(f"{filename}|{old_filename}|{filesize}".encode())
                        sock.recv(128)

                        with open(filepath, 'rb') as f:
                            while True:
                                bytes_read = f.read(self.buffer_size)
                                if not bytes_read:
                                    break
                                sock.sendall(bytes_read)
                        print(f"{filename} sent back to server.")
                        with self.shared_resource.lock:
                            self.shared_resource.completed_files.pop(0)
                        os.remove(filepath)
                        os.remove(os.path.join(os.getcwd(),self.watch_folder, old_filename))
                except Exception as e:
                    print(f"Failed to send {filename} back to server: {e}")
            time.sleep(1)

    def process_video_file(self):
        while self.running:
            if self.shared_resource.files:
                data = self.shared_resource.files[0]
                filename,options,burnSubtitles= data[0],data[1],data[2]
                subtitle_string=""
                cwd = os.getcwd()
                print(cwd)

                inputfile = os.path.join(self.watch_folder, filename)
                outputfile=os.path.join(self.fin_folder, filename.split(".")[0])
                print(inputfile)

                if burnSubtitles != "NIL":
                    subtitlefilter_input = "{}/{}".format(self.watch_folder.replace("\\","/"),filename)
                    desired_language = burnSubtitles.split(",")
                    ffprobe_command = f'ffprobe -v error -select_streams s -show_entries stream_tags=language -of csv=p=0 -i "{inputfile}"'
                    result = subprocess.run(ffprobe_command, capture_output=True,text=True,cwd=cwd)
                    stream_index = None
                    for x,line in enumerate(result.stdout.splitlines()):
                        if line.strip() in desired_language:
                            stream_index = x
                            break

                    if stream_index is None:
                        subtitle_string=""
                        print("missing index")
                    else:
                        subtitle_string=f'-vf subtitles="{subtitlefilter_input}":si={stream_index} '

                command_string = f'ffmpeg -y -v error -i "{inputfile}" {subtitle_string}{options} "{outputfile}.mp4"'
                # print("dsadsadsadasdads==============================================================================")
                if subprocess.run(command_string,text=True, cwd=cwd).returncode == 0:
                    print ("FFmpeg Script Ran Successfully")
                    with self.shared_resource.lock:
                        self.shared_resource.files.pop(0)
                        self.shared_resource.completed_files.append([filename,"{}.mp4".format(filename.split(".")[0])])
                else:
                    print ("There was an error running your FFmpeg script")
            time.sleep(1)

    def stop(self):
        self.running = False
        self.send_thread.join()
        self.receive_thread.join()
        self.process_thread.join()

class NodeDiscovery(threading.Thread):
    def __init__(self, discovery_port, transfer_recv_port,shared_resource,magicString):
        self.discovery_port = discovery_port
        self.magicString = magicString
        self.transfer_recv_port = transfer_recv_port
        self.running = True
        self.shared_resource= shared_resource
        threading.Thread.__init__(self)

    def run(self):
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.bind(('', self.discovery_port))
            # sock.setblocking(False)
            sock.settimeout(10)
            print(f"Listening for node announcements on port {self.discovery_port}")

            while self.running:
                try:
                    if self.shared_resource.connected:
                        data, addr = sock.recvfrom(1024)
                        data = data.decode().split(",")
                        if data[0] == self.magicString:
                            if data[1] == "ping":
                                sock.sendto("hi",addr)
                                continue
                            if data[1] == "serveroffline":
                                self.shared_resource.connected = False
                                self.shared_resource.server_addr = None
                                print(f"Server Offline. Finding server every 10s")
                                sock.settimeout(10)
                                continue
                            if data[1] == "shutdown":
                                subprocess.run("shutdown /s /t 10")
                    else:
                        sock.sendto("{},online,{}".format(self.magicString,self.transfer_recv_port).encode(), ("255.255.255.255", 49152))
                        data, addr = sock.recvfrom(1024)
                        servertcpport = int(data.decode().split(",")[2])
                        self.shared_resource.server_addr = [addr[0],addr[1],servertcpport]
                        sock.sendto(f"{self.magicString},messageReceived".encode(), addr)
                        sock.settimeout(1)
                        self.shared_resource.connected= True
                        print(f"Server Online: {self.shared_resource.server_addr}")
                        
                except BlockingIOError:
                    continue
                except socket.timeout:
                    continue
            if self.shared_resource.connected:
                sock.sendto("{},offline,{}".format(self.magicString,self.transfer_recv_port).encode(), ("255.255.255.255", 49152))
    def stop(self):
        self.running = False



def main():
    # Add config handler here
    #
    config = configparser.ConfigParser()
    config.read("config_node.txt")

    discovery_port = int(config['DiscoverySocket']['discoveryPort'])
    magicString = config['DiscoverySocket']['magicString']
    transfer_recv_port = int(config['TransferSocket']['recvPort'])

    shared_resource = SharedResource()
    watch_folder = config['Folders']['recv_folder']
    fin_folder = config['Folders']['processed_folder']

    if not os.path.isdir(watch_folder):
        os.mkdir(watch_folder)
    if not os.path.isdir(fin_folder):
        os.mkdir(fin_folder)

    video_transfer_server = VideoTransferNode('0.0.0.0', shared_resource,transfer_recv_port,watch_folder,fin_folder)
    node_discovery = NodeDiscovery(discovery_port, transfer_recv_port,shared_resource,magicString)


    node_discovery.start()

    try:
        while True:
            # just to keep the while loop from running
            # any number for sleep ok
            time.sleep(600)
    except KeyboardInterrupt:
        s = signal.signal(signal.SIGINT, signal.SIG_IGN)
        print("Interrupt received, stopping services.")     
        video_transfer_server.stop()
        node_discovery.stop()
        node_discovery.join()
        signal.signal(signal.SIGINT, s)


if __name__ == "__main__":
    main()
