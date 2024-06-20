# Distributed transcoding thing (DTT)
Simple distributed transcoding python script. Why? coz i didnt like the additional features of tdarr and just wanted to run a stripped down version of it. Think of it as bare essentials.

HOWEVER, if you are looking for something professional, something not jank. dont use this. I CANNOT guarantee the security of the program so **use at your own risk**. It is NOT intended to be used with ports forwarded to the internet. Also program might break so create a issue or something with a solution.

## Installation and usage

Requirements:
FFmpeg (make sure is installed on system. cannot set path to it in program config)
FFprobe (make sure is installed on system. cannot set path to it in program config)
Python >= 3.9 ( its the lowest i tested on)

Run the command:
```pip install -r requirements```
For both the server and node

To run the scripts:
```
python server.py
python node.py
```
on the respective systems running node and server.

Server.py allows the following arguments
`-c, --check-watch-folder-startup` This just checks the watch folder on start up for video files

CONFIG FILES HAVE COMMENTS. read it to see what each config does.
server has an auto node startup/shutdown thing. however do note that it requires the `etherwake` command installed on the server system and wakeonlan to be enabled on the node system. IT IS DISABLED BY DEFAULT. enable it at your own risk.
