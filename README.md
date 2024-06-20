# Distributed transcoding thing (DTT)
Simple distributed transcoding python script. Why? coz i didnt like the additional features of tdarr and just wanted to run a stripped down version of it. Think of it as bare essentials.

HOWEVER, if you are looking for something professional, something not jank. dont use this. I CANNOT guarantee the security of the program so **use at your own risk**. It is NOT intended to be used with ports forwarded to the internet. Also program might break so create a issue or something with a solution.

## Installation and usage
IMPORTANT TO NOTE. ONLY PUT COMPLETED DOWNLOADED FILES INTO THE WATCH FOLDER. the program will cause issues if the files in the watch folder is incomplete ( ie stll being downloaded directly to the watch folder.) 
Set up your downloaders to only put the files into the watch folder when the file download is completed.

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

Do note that there is no GUI or web UI of any kind.

CONFIG FILES HAVE COMMENTS. read it to see what each config does.
server has an auto node startup/shutdown thing. however do note that it requires the `etherwake` command installed on the server system and wakeonlan to be enabled on the node system. IT IS DISABLED BY DEFAULT. enable it at your own risk.
if u do enable it, make sure node.py is being run on startup using task scheduler or something.
To terminate the file, do ctrl + c (keyboard interrupt) in terminal

## my personal use case (story time)
I run jellyfin on a raspberry pi 4 4gb. That thing dont have enough power to transcode anything. and idk for some reason subtitles dont work well on jellyfin ( at least to my liking ). I do however have a pc that has a decent gpu in it but i dont want to keep it running 24/7.
so i made this to turn on my pc on a schedule to transcode the videos queued up on the raspberry pi. since i probably would only run this when im sleeping, i want it to auto shutdown my pc as well once its done. so ya.  
anyways, if it concerns you. my raspberry pi is running pi os legacy ( the one where realvnc is still usable ) and my pc is running windows 10.
