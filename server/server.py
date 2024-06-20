import socket
import configparser
import threading
import socket
import os
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import time
import signal
import schedule
import argparse
import subprocess
import json

class SharedResource:
    def __init__(self):
        self.files = []
        self.files_tbc = []
        self.node_addresses = []
        self.lock = threading.Lock()
        self.discovery_port = 0
        self.transfer_recv_port = 0
        self.ffmpeg_options=""
        self.burn_subtitles="NIL"
        self.scheduler_flag=False
        self.scheduler_enabled=False

class FileWatcher(threading.Thread):
    def __init__(self, folder_path, shared_resource):
        self.observer = Observer()
        self.folder_path = folder_path
        self.shared_resource = shared_resource
        threading.Thread.__init__(self)

    def on_created(self, event):
        # TODO check if video is already in wanted codec and bitrate
        with self.shared_resource.lock:
            self.shared_resource.files.append(os.path.join(os.getcwd,event.src_path))
            print(f"Added to queue: {event.src_path}")

    def run(self):
        event_handler = FileSystemEventHandler()
        event_handler.on_created = self.on_created
        self.observer.schedule(event_handler, self.folder_path, recursive=False)
        self.observer.start()

    def stop(self):
        self.observer.stop()  # Tell the observer to stop watching
        self.observer.join()  # Wait for the observer to finish
        print("File watching stopped.")

class VideoTransferServer():
    def __init__(self, host, shared_resource,folder_path,encoded_folder_path):
        # threading.Thread.__init__(self)
        self.folder_path = folder_path
        self.encoded_folder_path = encoded_folder_path
        self.host = host
        self.receive_port = shared_resource.transfer_recv_port
        self.shared_resource = shared_resource
        self.buffer_size = 4096
        self.running = True
        self.send_thread = threading.Thread(target=self.run)
        self.receive_thread = threading.Thread(target=self.receive_video_files)
        self.receive_thread.start()
        self.send_thread.start()


    def run(self):
        # recode this so that lock is only used when updating filename array
        while self.running:
            n=0
            while self.shared_resource.files:
                if not self.shared_resource.node_addresses:
                    # print("No node addresses available.")
                    break
                # ADD FILE DISTRIBUTION HERE ===================================================================================================
                with self.shared_resource.lock:
                    file_path = self.shared_resource.files.pop(0)
                    self.shared_resource.files_tbc.append(file_path)
                node_address = self.shared_resource.node_addresses[n]  # Example: Using the first available node address
                n = (n+1)%len(self.shared_resource.node_addresses) #file distribution?
                self.send_video_to_node((node_address[0],node_address[2]), file_path)
            time.sleep(5)


    def send_video_to_node(self, node_address, file_path):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.connect(node_address)
                file_size = os.path.getsize(file_path)
                options = f"{self.shared_resource.ffmpeg_options}".encode("ascii")
                burn_subtitles =f"{self.shared_resource.burn_subtitles}".encode("ascii")
                if len(options)>self.buffer_size:
                    raise Exception(f"Options char length more than buff size of {self.buffer_size} characters. Reduce options length or change buffer size in code. Class VideoTransferServer. Function __init__")
                sock.sendall(f"{os.path.basename(file_path)}|{file_size}".encode())
                sock.recv(128)
                sock.sendall(options)
                sock.recv(128)
                sock.sendall(burn_subtitles)
                sock.recv(128)

                with open(file_path, 'rb') as file:
                    while True:
                        bytes_read = file.read(self.buffer_size)
                        if not bytes_read:
                            break
                        sock.sendall(bytes_read)
                print(f"File {os.path.basename(file_path)} has been sent to {node_address}.")
        except Exception as e:
            print(f"Failed to send video {os.path.basename(file_path)} to {node_address}: {e}")

    def receive_video_files(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind((self.host, self.receive_port))
            sock.listen(5)
            sock.settimeout(1)
            print(f"Listening for completed videos on port {self.receive_port}")

            while self.running:
                try:
                    client_socket, addr = sock.accept()
                    print(f"Connection from {addr}")
                    received = client_socket.recv(self.buffer_size).decode()
                    if not received:
                        continue
                    filename, old_filename,filesize = received.split('|')
                    filename = os.path.join(self.encoded_folder_path, filename)  # Save in the same watched folder or a different one
                    filesize = int(filesize)
                    
                    client_socket.sendall(b'recv')

                    with open(filename, 'wb') as f:
                        while filesize > 0:
                            bytes_read = client_socket.recv(self.buffer_size)
                            if not bytes_read:
                                break
                            f.write(bytes_read)
                            filesize -= len(bytes_read)
                    print(f"Received completed video {filename} from {addr}")
                    os.remove(os.path.join(self.folder_path,old_filename))
                    with self.shared_resource.lock:
                        self.shared_resource.files_tbc.remove(old_filename)
                except socket.timeout:
                    continue

    def stop(self):
        self.running = False
        self.send_thread.join()
        self.receive_thread.join()

class NodeDiscovery(threading.Thread):
    def __init__(self,shared_resource,magicString):
        self.transfer_recv_port=shared_resource.transfer_recv_port
        self.port = shared_resource.discovery_port
        self.shared_resource = shared_resource
        self.running = True
        self.magicString = magicString
        threading.Thread.__init__(self)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(('0.0.0.0', self.port))
        self.sock.settimeout(1)
        print(f"Listening for node announcements on port {self.port}")


    def run(self):
        while self.running:
            try:
                data, addr = self.sock.recvfrom(1024)
                node_address = addr
                with self.shared_resource.lock:
                    data = data.decode().split(",")
                    if data[0] == self.magicString:
                        if data[1] == "online":
                            node_port = int(data[2])
                            new_addr = [node_address[0],node_address[1],node_port]
                            if not (new_addr in self.shared_resource.node_addresses):
                                # check magic string to make sure that it is actally the node program
                                # get file transferserver port number from data
                                self.shared_resource.node_addresses.append(new_addr)
                                print(f"Node online: {node_address}")
                                self.sock.sendto("{},messageReceived,{}".format(self.magicString,self.transfer_recv_port).encode(),addr)
                            continue

                        if data[1] == "offline":
                            node_port = int(data[2])
                            new_addr = [node_address[0],node_address[1],node_port]
                            if new_addr in self.shared_resource.node_addresses:
                                # check magic string to make sure that it is actally the node program
                                # get file transferserver port number from data
                                self.shared_resource.node_addresses.remove(new_addr)
                                print(f"Node Offline: {node_address}")
                            continue
                                

            except BlockingIOError:
                continue
            except socket.timeout:
                continue
        for addr in self.shared_resource.node_addresses:
            self.sock.sendto("{},serveroffline,{}".format(self.magicString,self.transfer_recv_port).encode(),(addr[0],addr[1]))
        self.sock.close()
    def stop(self):
        self.running = False
    
    def shutdown_node(self):
        while self.shared_resource.node_addresses:
            addr = self.shared_resource.node_addresses.pop(0)
            self.sock.sendto(f"{self.magicString},shutdown".encode(),(addr[0],addr[1]))
            print(f"Node Shutdown: {addr}")

def start_schedule_check_node(shared_resource,config):
    if config["Schedule"]["enabled"].lower() == "true":
        shared_resource.scheduler_enabled = True
        mac_addresses = json.loads(config["Schedule"]["macAddr"])
        if config["Schedule"]["type"].lower() == "weekly":
            if config["Schedule"]["day"].lower() == "monday":
                schedule.every().monday.at(config["Schedule"]["time"].replace("-",":")).do(turn_on_node, mac_addresses=mac_addresses,shared_resource=shared_resource)
            elif config["Schedule"]["day"].lower() == "tuesday":
                schedule.every().tuesday.at(config["Schedule"]["time"].replace("-",":")).do(turn_on_node, mac_addresses=mac_addresses,shared_resource=shared_resource)
            elif config["Schedule"]["day"].lower() == "wednesday":
                schedule.every().wednesday.at(config["Schedule"]["time"].replace("-",":")).do(turn_on_node, mac_addresses=mac_addresses,shared_resource=shared_resource)
            elif config["Schedule"]["day"].lower() == "thursday":
                schedule.every().thursday.at(config["Schedule"]["time"].replace("-",":")).do(turn_on_node, mac_addresses=mac_addresses,shared_resource=shared_resource)
            elif config["Schedule"]["day"].lower() == "friday":
                schedule.every().friday.at(config["Schedule"]["time"].replace("-",":")).do(turn_on_node, mac_addresses=mac_addresses,shared_resource=shared_resource)
            elif config["Schedule"]["day"].lower() == "saturday":
                schedule.every().saturday.at(config["Schedule"]["time"].replace("-",":")).do(turn_on_node, mac_addresses=mac_addresses,shared_resource=shared_resource)
            elif config["Schedule"]["day"].lower() == "sunday":
                schedule.every().sunday.at(config["Schedule"]["time"].replace("-",":")).do(turn_on_node, mac_addresses=mac_addresses,shared_resource=shared_resource)
        elif config["Schedule"]["type"].lower() == "daily":
            schedule.every().day.at(config["Schedule"]["time"].replace("-",":")).do(turn_on_node, mac_addresses=mac_addresses,shared_resource=shared_resource)        
    return

def turn_on_node(shared_resource,mac_addresses):
    if shared_resource.files:
        for addr in mac_addresses:
            command = [
                "sudo", "etherwake",addr.replace('-',':')
            ]
            subprocess.run(command, text=True)
        shared_resource.scheduler_flag = True


def arg_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument('-c','--check-watch-folder-startup',action='store_true',help = "Check watch folder on startup for any files to send over to node")
    args = parser.parse_args()
    return args

def check_watch_folder(shared_resource,watch_folder):
    file_ext = ["mkv","mp4","mov","avi","webm","ts","m2ts"]
    for f in os.listdir(watch_folder):
        if os.isfile(os.join(watch_folder, f)):
            if f.split(".")[-1] in file_ext:
                shared_resource.append(os.join(os.getcwd,watch_folder,f))
    return



def main():
    args = arg_parser()
    config = configparser.ConfigParser()
    config.read("config_server.txt")
    shared_resource = SharedResource()

    shared_resource.discovery_port = int(config['DiscoverySocket']['discoveryPort'])
    magicString = config['DiscoverySocket']['magicString']
    shared_resource.transfer_recv_port = int(config['TransferSocket']['recvPort'])
    shared_resource.ffmpeg_options = config['ffmpeg']['optionString'].replace("~",":")
    if config['ffmpeg']['burnSubtitle']:
        shared_resource.burn_subtitles = config['ffmpeg']['burnSubtitle']

    start_schedule_check_node(shared_resource,config)

    folder_path = config['Folders']['watch_folder']
    encoded_folder_path = config['Folders']['encoded_folder']

    if not os.path.isdir(folder_path):
        os.mkdir(folder_path)
    if not os.path.isdir(encoded_folder_path):
        os.mkdir(encoded_folder_path)

    if args.check_watch_folder_startup:
        check_watch_folder(shared_resource,folder_path)

    file_watcher = FileWatcher(folder_path, shared_resource)
    video_transfer_server = VideoTransferServer('0.0.0.0', shared_resource,folder_path,encoded_folder_path)
    node_discovery = NodeDiscovery(shared_resource,magicString)

    file_watcher.start()
    node_discovery.start()

    try:
        
        while True:
            schedule.run_pending()
            if shared_resource.scheduler_flag and shared_resource.scheduler_enabled:
                while True:
                    if not shared_resource.files and not shared_resource.files_tbc:
                        node_discovery.shutdown_node()
                        break
                    time.sleep(5)
                shared_resource.scheduler_flag = False
                
            # just to keep the while loop from running
            # any number for sleep ok
            time.sleep(30)
    except KeyboardInterrupt:
        s = signal.signal(signal.SIGINT, signal.SIG_IGN)
        print("Interrupt received, stopping services.")
        file_watcher.stop()
        file_watcher.join()
        video_transfer_server.stop()
        node_discovery.stop()
        node_discovery.join()
        signal.signal(signal.SIGINT, s)



if __name__ == "__main__":
    main()
