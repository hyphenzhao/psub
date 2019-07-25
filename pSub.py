import hashlib
import os
import string
import sys
import time
import sys
import re
import json
import urllib
from random import SystemRandom, shuffle, choices
from subprocess import CalledProcessError, Popen
from threading import Thread
import datetime

import requests
from click import UsageError

try:
    from queue import LifoQueue
except ImportError:
    from Queue import LifoQueue  # noqa

import click
import yaml


class pSub(object):
    """
    pSub Object interfaces with the Subsonic server and handles streaming media
    """
    def __init__(self, config):
        """
        Load the config, creating it if it doesn't exist.
        Test server connection
        Start background thread for getting user input during streaming
        :param config: path to config yaml file
        """
        # If no config file exists we should create one and
        if not os.path.isfile(config):
            self.set_default_config(config)
            click.secho('Welcome to pSub', fg='green')
            click.secho('To get set up, please edit your config file', fg='red')
            click.pause()
            click.edit(filename=config)

        # load the config file
        with open(config) as config_file:
            config = yaml.safe_load(config_file)

        # Get the Server Config
        server_config = config.get('server', {})
        self.host = server_config.get('host')
        self.username = server_config.get('username', '')
        self.password = server_config.get('password', '')
        self.ssl = server_config.get('ssl', False)

        # get the streaming config
        streaming_config = config.get('streaming', {})
        self.video_format = streaming_config.get('format', 'raw')
        self.music_format = streaming_config.get('format', 'raw')
        self.display = streaming_config.get('display', False)
        self.show_mode = streaming_config.get('show_mode', 0)
        self.invert_random = streaming_config.get('invert_random', False)

        # use a Queue to handle command input while a file is playing.
        # set the thread going now
        self.input_queue = LifoQueue()
        input_thread = Thread(target=self.add_input)
        input_thread.daemon = True
        input_thread.start()

        # remove the lock file if one exists
        if os.path.isfile(os.path.join(click.get_app_dir('pSub'), 'play.lock')):
            os.remove(os.path.join(click.get_app_dir('pSub'), 'play.lock'))

    def test_config(self):
        """
        Ping the server specified in the config to ensure we can communicate
        """
        click.secho('Testing Server Connection', fg='green')
        click.secho(
            '{}://{}@{}'.format(
                'https' if self.ssl else 'http',
                self.username,
                self.host,
            ),
            fg='blue'
        )
        ping = self.make_request(url=self.create_url('ping'))
        if ping:
            click.secho('Test Passed', fg='green')
            return True
        else:
            click.secho('Test Failed! Please check your config', fg='black', bg='red')
            return False

    def hash_password(self):
        """
        return random salted md5 hash of password
        """
        characters = string.ascii_uppercase + string.ascii_lowercase + string.digits
        salt = ''.join(SystemRandom().choice(characters) for i in range(9))
        salted_password = self.password + salt
        token = hashlib.md5(salted_password.encode('utf-8')).hexdigest()
        return token, salt

    def create_url(self, endpoint):
        """
        build the standard url for interfacing with the Subsonic REST API
        :param endpoint: REST endpoint to incorporate in the url
        """
        token, salt = self.hash_password()
        url = '{}://{}/rest/{}?u={}&t={}&s={}&v=1.16.0&c=pSub&f=json'.format(
            'https' if self.ssl else 'http',
            self.host,
            endpoint,
            self.username,
            token,
            salt
        )
        return url

    @staticmethod
    def make_request(url):
        """
        GET the supplied url and resturn the response as json.
        Handle any errors present.
        :param url: full url. see create_url method for details
        :return: Subsonic response or None on failure
        """
        try:
            r = requests.get(url=url)
        except requests.exceptions.ConnectionError as e:
            click.secho('{}'.format(e), fg='red')
            sys.exit(1)

        try:
            response = r.json()
        except ValueError:
            response = {
                'subsonic-response': {
                    'error': {
                        'code': 100,
                        'message': r.text
                    },
                    'status': 'failed'
                }
            }

        subsonic_response = response.get('subsonic-response', {})
        status = subsonic_response.get('status', 'failed')

        if status == 'failed':
            error = subsonic_response.get('error', {})
            click.secho(
                'Command Failed! {}: {}'.format(
                    error.get('code', ''),
                    error.get('message', '')
                ),
                fg='red'
            )
            return None

        return response

    def scrobble(self, song_id):
        """
        notify the Subsonic server that a track is being played within pSub
        :param song_id:
        :return:
        """
        self.make_request(
            url='{}&id={}'.format(
                self.create_url('scrobble'),
                song_id
            )
        )

    def search(self, query):
        """
        search using query and return the result
        :return:
        :param query: search term string
        """
        results = self.make_request(
            url='{}&query={}'.format(self.create_url('search3'), query)
        )
        if results:
            return results['subsonic-response']['searchResult3']
        return []

    def get_artists(self):
        """
        Gather list of Artists from the Subsonic server
        :return: list
        """
        artists = self.make_request(url=self.create_url('getArtists'))
        if artists:
            return artists['subsonic-response']['artists']['index']
        return []

    def get_playlists(self):
        """
        Get a list of available playlists from the server
        :return:
        """
        playlists = self.make_request(url=self.create_url('getPlaylists'))
        if playlists:
            return playlists['subsonic-response']['playlists']['playlist']
        return []

    def get_music_folders(self):
        """
        Gather list of Music Folders from the Subsonic server
        :return: list
        """
        music_folders = self.make_request(url=self.create_url('getMusicFolders'))
        if music_folders:
            return music_folders['subsonic-response']['musicFolders']['musicFolder']
        return []

    def get_indexes(self, folder_id):
        indexes = self.make_request('{}&musicFolderId={}'.format(self.create_url('getIndexes'), str(folder_id)))
        if indexes:
            return indexes['subsonic-response']['indexes']
        return []

    def get_music_directory(self, dir_id):
        """
        Gather list of Music Directories from the Subsonic server
        :return: list
        """
        music_folders = self.make_request('{}&id={}'.format(self.create_url('getMusicDirectory'), str(dir_id)))
        if music_folders:
            return music_folders['subsonic-response']['directory']
        return []

    def get_album_tracks(self, album_id):
        """
        return a list of album track ids for the given album id
        :param album_id: id of the album
        :return: list
        """
        album_info = self.make_request('{}&id={}'.format(self.create_url('getAlbum'), album_id))
        songs = []

        for song in album_info['subsonic-response']['album']['song']:
            songs.append(song)

        return songs

    def get_videos(self):
        """
        Get a list of all videos
        :return: list
        """
        videos = self.make_request(url=self.create_url('getVideos'))

        if videos:
            return videos['subsonic-response']['videos']['video']
        return []

    def play_random_songs(self, music_folder):
        """
        Gather random tracks from the Subsonic server and playthem endlessly
        :param music_folder: integer denoting music folder to filter tracks
        """
        url = self.create_url('getRandomSongs')

        if music_folder != 0:
            url = '{}&musicFolderId={}'.format(url, music_folder)

        playing = True

        while playing:
            random_songs = self.make_request(url)

            if not random_songs:
                return

            for random_song in random_songs['subsonic-response']['randomSongs']['song']:
                if not playing:
                    return
                playing = self.play_stream(dict(random_song))

    def play_radio(self, radio_id):
        """
        Get songs similar to the supplied id and play them endlessly
        :param radio_id: id of Artist
        """
        playing = True
        while playing:
            similar_songs = self.make_request(
                '{}&id={}'.format(self.create_url('getSimilarSongs2'), radio_id)
            )

            if not similar_songs:
                return

            for radio_track in similar_songs['subsonic-response']['similarSongs2']['song']:
                if not playing:
                    return
                playing = self.play_stream(dict(radio_track))

    def play_artist(self, artist_id, randomise):
        """
        Get the songs by the given artist_id and play them
        :param artist_id:  id of the artist to play
        :param randomise: if True, randomise the playback order
        """
        artist_info = self.make_request('{}&id={}'.format(self.create_url('getArtist'), artist_id))
        songs = []

        for album in artist_info['subsonic-response']['artist']['album']:
            songs += self.get_album_tracks(album.get('id'))

        if self.invert_random:
            randomise = not randomise

        if randomise:
            shuffle(songs)

        playing = True

        while playing:
            for song in songs:
                if not playing:
                    return
                playing = self.play_stream(dict(song))

    def play_album(self, album_id, randomise):
        """
        Get the songs for the given album id and play them
        :param album_id:
        :param randomise:
        :return:
        """

        songs = self.get_album_tracks(album_id)

        if self.invert_random:
            randomise = not randomise

        if randomise:
            shuffle(songs)

        playing = True

        while playing:
            for song in songs:
                if not playing:
                    return
                playing = self.play_stream(dict(song))

    def play_video(self, videos_list, video_id):
        target_video = None
        for video in videos_list:
            if int(video.get('id')) == int(video_id):
                target_video = video
        if target_video:
            print(target_video)
        else:
            print("Cannot find video with id " + str(video_id))
        self.play_stream(target_video, is_video=True)

    def play_video_list(self, dir_id):
        directory = self.get_music_directory(dir_id)
        self.show_banner("Play videos in <" + directory.get('name') + ">")
        if 'child' in directory:
            directory = directory['child']
            videos = []
            for i in directory:
                if (i.get('isDir') == 'false' or i.get('isVideo')):
                    videos.append(i)
            if len(videos) == 0:
                print('No medias.')
                return
            playing = True
            while playing:
                i = 0
                while i < len(videos): 
                    video = videos[i]
                    if not playing:
                        return
                    playing = self.play_stream(dict(video), is_video=True)
                    if playing == 'previous':
                        if i != 0:
                            i -= 1
                        else:
                            i = len(songs) - 1
                        playing = True
                        continue
                    i += 1
        else:
            print('Nothing here.')

    def play_playlist(self, playlist_id, randomise):
        """
        Get the tracks from the supplied playlist id and play them
        :param playlist_id:
        :param randomise:
        :return:
        """
        playlist_info = self.make_request(
            url='{}&id={}'.format(self.create_url('getPlaylist'), playlist_id)
        )
        songs = playlist_info['subsonic-response']['playlist']['entry']

        if self.invert_random:
            randomise = not randomise

        if randomise:
            shuffle(songs)

        playing = True

        while playing:
            i = 0
            while i < len(songs): 
                song = songs[i]
                if not playing:
                    return
                playing = self.play_stream(dict(song))
                if playing == 'previous':
                    if i != 0:
                        i -= 1
                    else:
                        i = len(songs) - 1
                    playing = True
                    continue
                i += 1

    def randomString(self, stringLength=10):
        """Generate a random string of fixed length """
        return ''.join(choices(string.ascii_lowercase + string.digits, k=stringLength))

    def get_songs_id_list(self, song_name):
        # Load songs id list
        song_possible_names = []
        song_possible_names.append(song_name)
        sub_names = re.split(r'[-,.()|/]+', song_name)
        if len(sub_names) > 1:
            song_possible_names = song_possible_names + sub_names
        netease_url = "http://music.163.com/api/search/pc"
        limit = 3
        songs_id_list = []
        for i in song_possible_names:
            possible_name = i.strip()
            if possible_name:
                print("Searching name as <" + possible_name + "> ...")
                params = {'s':possible_name, 'offset':0, 'limit':limit, 'type':1}
                result = requests.post(url=netease_url, params=params)
                if 'result' in result.json() and 'songCount' in result.json()['result']:
                    if result.json()['result']['songCount'] != 0:
                        song_info = result.json()['result']
                        amount = min(song_info['songCount'], limit)
                        if amount == 0:
                            continue
                        for j in range(amount):
                            songs_id_list.append(song_info['songs'][j]['id'])            
        return songs_id_list

    def load_lyric_for(self, song_id):
        lyric_url = "http://music.163.com/api/song/media?id=" + str(song_id)
        print("Lyric Url:" + lyric_url)
        lyric = requests.get(lyric_url)
        if 'lyric' in lyric.json():
            return lyric.json()['lyric']
        elif 'msg' in lyric.json() and lyric.json()['msg'] == 'Cheating':
            return 'IP blocked...'
        else:
            return 'Pure musics, please enjoy.'

    def play_stream(self, track_data, is_video=False):
        """
        Given track data, generate the stream url and pass it to ffplay to handle.
        While stream is playing allow user input to control playback
        :param track_data: dict
        :return:
        """
        stream_url = self.create_url('stream')
        song_id = track_data.get('id')

        if not song_id:
            return False
        track_data_title = track_data.get('title', '')
        track_data_artist = track_data.get('artist', '')
        if sys.version_info[0] < 3:
            track_data_title = track_data_title.encode('utf-8')
            track_data_artist = track_data_artist.encode('utf-8')
        if is_video:
            present_title = '{}'.format(
                track_data_title
            )
        else:
            present_title = '{} by {}'.format(
                track_data_title,
                track_data_artist
            )
        click.secho(
            present_title,
            fg='green'
        )

        self.scrobble(song_id)
        if is_video:
            x = str(track_data.get('originalWidth'))
            y = str(track_data.get('originalHeight'))
        else:
            x = "500"
            y = "500"
        if is_video:
            media_format = self.video_format
        else:
            media_format = self.music_format
        params = [
            'ffplay',
            '-i',
            '{}&id={}&format={}'.format(stream_url, song_id, media_format),
            '-showmode',
            '{}'.format(self.show_mode),
            '-window_title',
            present_title,
            '-autoexit',
            '-hide_banner',
            '-x',
            x,
            '-y',
            y,
            '-loglevel',
            'fatal',
        ]
        if not self.display and not is_video:
            params += ['-nodisp']

        try:
            ffplay = Popen(params)

            has_finished = None
            open(os.path.join(click.get_app_dir('pSub'), 'play.lock'), 'w+').close()

            if not is_video:
                # Load song lyrics
                songs_id_list = self.get_songs_id_list(track_data_title)
                lyrics_no = 0
                if songs_id_list:
                    print("Lyrics available amount: " + str(len(songs_id_list)))
                    lyrics = self.load_lyric_for(songs_id_list[lyrics_no])
                    print(lyrics)
                else:
                    print("Network error. Please check your internet connection.")


            while has_finished is None:
                has_finished = ffplay.poll()
                if self.input_queue.empty():
                    time.sleep(1)
                    continue

                command = self.input_queue.get_nowait()
                if sys.version_info[0] < 3:
                	del self.input_queue.queue[:]
                else:
                	self.input_queue.queue.clear()

                if 'x' in command.lower():
                    click.secho('Exiting!', fg='blue')
                    os.remove(os.path.join(click.get_app_dir('pSub'), 'play.lock'))
                    ffplay.terminate()
                    return False

                if 'b' in command.lower():
                    click.secho('Restarting Track....', fg='blue')
                    os.remove(os.path.join(click.get_app_dir('pSub'), 'play.lock'))
                    ffplay.terminate()
                    return self.play_stream(track_data)

                if 'n' in command.lower():
                    click.secho('Skipping...', fg='blue')
                    os.remove(os.path.join(click.get_app_dir('pSub'), 'play.lock'))
                    ffplay.terminate()
                    return True

                if 'v' in command.lower():
                    click.secho('Getting back...', fg='blue')
                    os.remove(os.path.join(click.get_app_dir('pSub'), 'play.lock'))
                    ffplay.terminate()
                    return "previous"

                if 'l' in command.lower():
                    if not is_video:
                        lyrics_no += 1
                        lyrics_no = lyrics_no % len(songs_id_list)
                        print(self.load_lyric_for(songs_id_list[lyrics_no]))
                    else:
                        print("This is a video, cannot load lyrics")
                    

            os.remove(os.path.join(click.get_app_dir('pSub'), 'play.lock'))
            return True

        except OSError:
            click.secho(
                'Could not run ffplay. Please make sure it is installed',
                fg='red'
            )
            click.launch('https://ffmpeg.org/download.html')
            return False
        except CalledProcessError as e:
            click.secho(
                'ffplay existed unexpectedly with the following error: {}'.format(e),
                fg='red'
            )
            return False

    def add_input(self):
        """
        This method runs in a separate thread (started in __init__).
        When the play.lock file exists it waits for user input and wrties it to a Queue.
        The play_stream method above deals with the user input when it occurs
        """
        while True:
            if not os.path.isfile(os.path.join(click.get_app_dir('pSub'), 'play.lock')):
                continue
            time.sleep(1)
            self.input_queue.put(click.prompt('', prompt_suffix=''))

    @staticmethod
    def show_banner(message):
        """
        Show a standardized banner with custom message and controls for playback
        :param message:
        """
        click.clear()
        click.echo('')
        click.secho('   {}   '.format(message), bg='blue', fg='black')
        click.echo('')
        click.secho('n = Next\nb = Beginning\nx = Exit\nl = Next Lyric\nv = Previous Song', bg='yellow', fg='black')
        click.echo('')

    @staticmethod
    def set_default_config(config):
        """
        When no config file is detected, this method is run to write the default config
        :param config: path to config file
        """
        with open(config, 'w+') as config_file:
            config_file.write(
                """#
#          _________    ___.
#  ______ /   _____/__ _\_ |__
#  \____ \\\_____  \|  |  \ __ \
#  |  |_> >        \  |  / \_\ \\
#  |   __/_______  /____/|___  /
#  |__|          \/          \/
#
#

# This section defines the connection to your Subsonic server

server:
    # This is the url you would use to access your Subsonic server without the protocol
    # (http:// or https://)

    host: demo.subsonic.org

    # Username and Password next

    username: username
    password: password

    # If your Subsonic server is accessed over https:// set this to 'true'

    ssl: false


# This section defines the playback of music by pSub

streaming:

    # The default format is 'raw'
    # this means the original file is streamed from your server
    # and no transcoding takes place.
    # set this to mp3 or wav etc.
    # depending on the transcoders available to your user on the server

    video_format: raw
    music_format: raw

    # pSub utilises ffplay (https://ffmpeg.org/ffplay.html) to play the streamed media
    # by default the player window is hidden and control takes place through the cli
    # set this to true to enable the player window.
    # It allows for more controls (volume mainly) but will grab the focus of your
    # keyboard when tracks change which can be annoying if you are typing

    display: true

    # When the player window is shown, choose the default show mode
    # Options are:
    # 0: show video or album art
    # 1: show audio waves
    # 2: show audio frequency band using RDFT ((Inverse) Real Discrete Fourier Transform)

    show_mode: 0

    # Artist, Album and Playlist playback can accept a -r/--random flag.
    # by default, setting the flag on the command line means "randomise playback".
    # Setting the following to true will invert that behaviour so that playback is randomised by default
    # and passing the -r flag skips the random shuffle

    invert_random: false

"""
            )


# _________ .____    .___
# \_   ___ \|    |   |   |
# /    \  \/|    |   |   |
# \     \___|    |___|   |
#  \______  /_______ \___|
#         \/        \/
# Below are the CLI methods

CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])


@click.group(
    invoke_without_command=True,
    context_settings=CONTEXT_SETTINGS
)
@click.pass_context
@click.option(
    '--config',
    '-c',
    is_flag=True,
    help='Edit the config file'
)
@click.option(
    '--test',
    '-t',
    is_flag=True,
    help='Test the server configuration'
)
def cli(ctx, config, test):
    if not os.path.exists(click.get_app_dir('pSub')):
        os.mkdir(click.get_app_dir('pSub'))

    config_file = os.path.join(click.get_app_dir('pSub'), 'config.yaml')
    # /Users/haifengzhao/Library/Application Support/pSub/config.yaml
    print(config_file)

    if config:
        test = True

        try:
            click.edit(filename=config_file, extension='yaml')
        except UsageError:
            click.secho('pSub was unable to open your config file for editing.', bg='red', fg='black')
            click.secho('please open {} manually to edit your config file'.format(config_file), fg='yellow')
            return

    ctx.obj = pSub(config_file)

    if test:
        # Ping the server to check server config
        test_ok = ctx.obj.test_config()
        if not test_ok:
            return

    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


pass_pSub = click.make_pass_decorator(pSub)


@cli.command(help='Play random tracks')
@click.option(
    '--music_folder',
    '-f',
    type=int,
    help='Specify the music folder to play random tracks from.',
)
@pass_pSub
def random(psub, music_folder):
    if not music_folder:
        music_folders = [{'name': 'All', 'id': 0}] + psub.get_music_folders()
        click.secho(
            '\n'.join(
                '{}\t{}'.format(folder['id'], folder['name']) for folder in music_folders
            ),
            fg='yellow'
        )
        music_folder = click.prompt(
            'Choose a music folder from the options above',
            default=0
        )

    psub.show_banner('Playing Random Tracks')
    psub.play_random_songs(music_folder)


@cli.command(help='Play endless Radio based on a search')
@click.argument('search_term')
@pass_pSub
def radio(psub, search_term):
    radio_id = None

    while not radio_id:
        results = psub.search(search_term)
        click.secho('Artists', bg='red', fg='black')
        click.secho(
            '\n'.join(
                '{}\t{}'.format(
                    str(artist.get('id')).ljust(7),
                    str(artist.get('name')).ljust(30),
                ) for artist in results.get('artist', [])
            ),
            fg='yellow'
        )

        radio_id = click.prompt(
            'Enter an id to start radio or Enter to search again',
            type=int,
            default=0,
            show_default=False
        )

        if not radio_id:
            search_term = click.prompt('Enter a new search')

    psub.show_banner('Playing Radio')

    psub.play_radio(radio_id)


@cli.command(help='Play songs from chosen Artist')
@click.argument('search_term')
@click.option(
    '--randomise',
    '-r',
    is_flag=True,
    help='Randomise the order of track playback',
)
@pass_pSub
def artist(psub, search_term, randomise):
    artist_id = None
    results = {}

    while not artist_id:
        results = psub.search(search_term)
        click.secho('Artists', bg='red', fg='black')
        click.secho(
            '\n'.join(
                '{}\t{}'.format(
                    str(artist.get('id')).ljust(7),
                    str(artist.get('name')).ljust(30),
                ) for artist in results.get('artist', [])
            ),
            fg='yellow'
        )

        artist_id = click.prompt(
            'Enter an id to start or Enter to search again',
            default=0,
            type=int,
            show_default=False
        )

        if not artist_id:
            search_term = click.prompt('Enter an artist name to search again')

    psub.show_banner(
        'Playing {} tracks by {}'.format(
            'randomised' if randomise else '',
            ''.join(
                artist.get('name') for artist in results.get('artist', []) if int(artist.get('id')) == int(artist_id)
            )
        )
    )

    psub.play_artist(artist_id, randomise)


@cli.command(help='Play songs from chosen Album')
@click.argument('search_term')
@click.option(
    '--randomise',
    '-r',
    is_flag=True,
    help='Randomise the order of track playback',
)
@pass_pSub
def album(psub, search_term, randomise):
    album_id = None
    results = {}

    while not album_id:
        results = psub.search(search_term)
        click.secho('Albums', bg='red', fg='black')
        click.secho(
            '\n'.join(
                '{}\t{}\t{}'.format(
                    str(album.get('id')).ljust(7),
                    str(album.get('artist')).ljust(30),
                    album.get('name')
                ) for album in results.get('album', [])
            ),
            fg='yellow'
        )

        album_id = click.prompt(
            'Enter an id to start or Enter to search again',
            type=int,
            default=0,
            show_default=False
        )

        if not album_id:
            search_term = click.prompt('Enter an album name to search again')

    psub.show_banner(
        'Playing {} tracks from {}'.format(
            'randomised' if randomise else '',
            ''.join(
                album.get('name') for album in results.get('album', []) if int(album.get('id')) == int(album_id)
            )
        )
    )

    psub.play_album(album_id, randomise)


@cli.command(help='Play a chosen playlist')
@click.option(
    '--randomise',
    '-r',
    is_flag=True,
    help='Randomise the order of track playback',
)
@pass_pSub
def playlist(psub, randomise):
    playlist_id = None

    while not playlist_id:
        playlists = psub.get_playlists()
        click.secho('Playlists', bg='red', fg='black')
        click.secho(
            '\n'.join(
                '{}\t{}\t{} tracks'.format(
                    str(playlist.get('id')).ljust(7),
                    str(playlist.get('name')).ljust(30),
                    playlist.get('songCount')
                ) for playlist in playlists
            ),
            fg='yellow'
        )

        playlist_id = click.prompt(
            'Enter an id to start',
            type=int,
        )

    psub.show_banner(
        'Playing {} tracks from the "{}" playlist'.format(
            'randomised' if randomise else '',
            ''.join(
                playlist.get('name') for playlist in playlists if int(playlist.get('id')) == int(playlist_id)
            )
        )
    )

    psub.play_playlist(playlist_id, randomise)

def check_id_exist(lists, check_id):
    for i in lists:
        if int(i.get('id')) == int(check_id):
            return i
    return False

@cli.command(help='Play a chosen TV series')
@pass_pSub
def video(psub):
    music_folder = None
    id_valid = False
    while not id_valid:
        music_folders = psub.get_music_folders()
        click.secho(
            '\n'.join(
                '{}\t{}'.format(folder['id'], folder['name']) for folder in music_folders
            ),
            fg='yellow'
        )
        music_folder = click.prompt(
            'Choose a music folder from the options above',
            default=0
        )
        for folder in music_folders:
            if int(folder['id']) == int(music_folder):
                id_valid = True
                break
    root_indexes = psub.get_indexes(music_folder)
    root_directory = root_indexes['index'] if 'index' in root_indexes else None
    root_videos = root_indexes['child'] if 'child' in root_indexes else None
    path_pos = 0
    path_history = []
    path_history.append(music_folder)
    user_command = None
    user_parameter = None
    while True:
        if path_pos == 0:
            all_artists = None
            if root_directory:
                all_artists = []
                for i in root_directory:
                    click.secho(i.get('name') + "\t\t", fg='white', bg='red')
                    artists = i['artist']
                    all_artists = all_artists + artists
                    click.secho(
                        '\n'.join(
                            '{}\t{}'.format(artist['id'], artist['name']) for artist in artists
                        ),
                        fg='yellow'
                    )
            if root_videos:
                click.secho(
                    '\n'.join(
                        '{}\t{}\t{}'.format(
                            str(video.get('id')).ljust(6), 
                            str(video.get('title')).ljust(16),
                            str(datetime.timedelta(seconds=video.get('duration'))) 
                        ) for video in root_videos
                    ),
                    fg='white',
                    bg='green'
                )
            user_input = click.prompt(
                'cd for directory, pl for play video or directory'
            )
            user_command, user_parameter = user_input.split(' ')
            if user_command == 'cd':
                if user_parameter == '..':
                    path_pos = max(0, path_pos - 1)
                elif all_artists and check_id_exist(all_artists, user_parameter):
                    path_pos += 1
                    if len(path_history) <= path_pos:
                        path_history.append(user_parameter)
                    else:
                        path_history[path_pos] = user_parameter
            elif user_command == 'pl':
                if root_videos and check_id_exist(root_videos, user_parameter):
                    psub.play_video(root_videos, user_parameter)
                    return
                elif all_artists and check_id_exist(all_artists, user_parameter):
                    psub.play_video_list(user_parameter)
                    return
            else:
                print('Wrong command.')
        else:
            directories = psub.get_music_directory(path_history[path_pos])
            if 'child' in directories:
                directories = directories['child']
            else:
                print('No medias here. Getting back...')
                path_pos -= 1
                continue
            for i in directories:
                if i.get('isDir') == 'true' or i.get('isDir'):
                    click.secho(
                        '{}\t{}\t{}'.format(
                            i.get('id').ljust(6),
                            i.get('title').ljust(16),
                            "Dir"
                        ),
                        fg='yellow'
                    )
                else:
                    duration = i.get('duration') if 'duration' in i else 0
                    click.secho(
                        '{}\t{}\t{}'.format(
                            i.get('id').ljust(6),
                            i.get('title').ljust(16),
                            str(datetime.timedelta(seconds=duration))
                        ),
                        fg='white',
                        bg='green'
                    )
            user_input = click.prompt(
                'cd for directory, pl for play video or directory'
            )
            user_command, user_parameter = user_input.split(' ')
            if user_command == 'cd':
                if user_parameter == '..':
                    path_pos = max(0, path_pos - 1)
                elif (check_id_exist(directories, user_parameter).get('isDir') == 'true' 
                    or check_id_exist(directories, user_parameter).get('isDir')):
                    path_pos += 1
                    if len(path_history) <= path_pos:
                        path_history.append(user_parameter)
                    else:
                        path_history[path_pos] = user_parameter
                else:
                    print(check_id_exist(directories, user_parameter))
            elif user_command == 'pl':
                if (check_id_exist(directories, user_parameter).get('isDir') == 'true' 
                    or check_id_exist(directories, user_parameter).get('isDir')):
                    psub.play_video_list(user_parameter)
                    return
                else:
                    psub.play_video(directories, user_parameter)
                    return
            else:
                print('Wrong command.')

# @cli.command(help='Play a chosen video')
# @pass_pSub
# def video(psub):
#     video_id = None
#     while not video_id:
#         videos = psub.get_videos()
#         click.secho('Videos', bg='red', fg='black')
#         click.secho(
#             '\n'.join(
#                 '{}\t{}'.format(
#                     str(video.get('id')).ljust(7),
#                     str(video.get('title'))
#                 ) for video in videos
#             ),
#             fg='yellow'
#         )
#         video_id = click.prompt(
#             'Enter an id to start',
#             type=int,
#         )

#     psub.play_video(videos, video_id)
    # psub.show_banner(
    #     'Playing {} tracks from the "{}" playlist'.format(
    #         'randomised' if randomise else '',
    #         ''.join(
    #             videos.get('name') for playlist in playlists if int(playlist.get('id')) == int(playlist_id)
    #         )
    #     )
    # )