```
          _________    ___.    
  ______ /   _____/__ _\_ |__  
  \____ \\_____  \|  |  \ __ \ 
  |  |_> >        \  |  / \_\ \
  |   __/_______  /____/|___  /
  |__|          \/          \/
   
```
## CLI Subsonic Client

Same as mj2p did, I was looking for an elegant Subsonic client but failed. I was then considering about building a command line client. But when I searched the github, I found this interesting project. As an innovation, I add more features based on the original [project](https://github.com/mj2p/psub). 

pSub is intended to be very simple and focus just on playing music easily. Don't expect to be able to access advanced configuration of a Subsonic server or playlist management.
  
pSub is written in Python (written with 3.5 but 2.7 should work) using [Click](http://click.pocoo.org/6/)  to build the CLI and [Requests](http://docs.python-requests.org) to handle the communication with the Subsonic API.  
It should run on most operating systems too but this hasn't been tested.   
   
### Installation
#### Dependencies
pSub uses [ffplay](https://ffmpeg.org/ffplay.html) to handle the streaming of music so that needs to be installed and available as a command line executable before using pSub. (you'll be prompted to download ffplay if pSub can't launch it correctly)
  
Python, pip and virtualenv also need to be installed
#### Instructions
(Tested on Ubuntu, other operating systems may vary)
- Clone this repo  
`git clone https://github.com/hyphenzhao/psub.git`
- Enter the pSub directory  
`cd psub`
- Create a virtualenv  
`virtualenv ve`  
or  
`python3 -m venv ve`  
- Install pSub  
`ve/bin/pip install .`
- Run pSub  
`ve/bin/pSub`  


### Usage
On first run you will be prompted to edit your config file. pSub will install a default config file and then open it for editing in your default text editor. You need to specify the url, username and password of your Subsonic server at a minimum.  
There are also some settings for adjusting your playback options. The settings are all described in detail in the config file itself.  
pSub will run a connection test once your config been saved to make sure it can communicate correctly with Subsonic.   
You can edit your config or run the connection test at any time with the -c and -t command line flags.

#### Commands
Once pSub is properly configured, you can start playing music by running any of the commands shown below.
```
Usage: pSub [OPTIONS] COMMAND [ARGS]...  

Options:  
  -c, --config  Edit the config file  
  -t, --test    Test the server configuration
  -h, --help    Show this message and exit.

Commands:
  album     Play songs from chosen Album
  artist    Play songs from chosen Artist
  playlist  Play a chosen playlist
  radio     Play endless Radio based on a search
  random    Play random tracks
  video     Play video or videos in a directory
```
#### Details
Here are some animations of the commands in action:  
##### album
`psub album` (functions involving a search will accept `*` as a wildcard)   
![](https://github.com/inuitwallet/psub/blob/images/album.gif)  
##### artist
`psub artist` (the `-r` flag indicates that tracks should be played back in a random order)  
![](https://github.com/inuitwallet/psub/blob/images/artist.gif)  
##### playlist
`psub playlist` (playlist must exist on the Subsonic server first)  
![](https://github.com/inuitwallet/psub/blob/images/playlist.gif)  
After entering into play mode, there will be a few more controls:

**n** Play next track.

**b** Restart current track.

**v** Play previous track.

**l** Show next lyric.

**x** Exit

Please note that the lyrics are acquired through [Netease Music](https://music.163.com/) API, which is basically a Chinese cloud music platform. Hence, most information is in Chinese.
##### radio
`psub radio`  
![](https://github.com/inuitwallet/psub/blob/images/radio.gif)
##### random  
`psub random`  
![](https://github.com/inuitwallet/psub/blob/images/random.gif)
##### video
You have to choose an directory entrace at the beginning. After you enter the root directory, it is similar to command in terminal.

**cd <Folder ID>** e.g. cd 4079, cd ..
          
**pl <ID>** Play videos or videos in the directory
