import requests
import re
import urllib
# lyrics_url = "http://geci.me/api/lyric/"            
# song_name = "幹物女(WeiWei)"
# lyrics_json = requests.get(lyrics_url + song_name).json()
# if lyrics_json['count'] == 0:
#     song_possible_names = re.split(r'[-,.()|/]+', song_name)
#     for i in song_possible_names:
#         possible_name = i.strip()
#         if possible_name:
#             print("Searching name as <" + possible_name + "> ...")
#             lyrics_json = requests.get(lyrics_url + possible_name).json()
#             if lyrics_json['count'] != 0:
#                 break
# if lyrics_json['count'] != 0:
#     lyric_url = lyrics_json['result'][0]['lrc']
#     lyric = urllib.request.urlopen(lyric_url)
#     for i in lyric:
#         print(i.decode('utf-8'))
# else:
#     print("No lyric was found!")
general_url = "http://music.163.com/api/search/pc"
params = {'s':'幹物女', 'offset':0, 'limit':1, 'type':1}
result = requests.post(url=general_url, params=params)
song_id = result.json()['result']['songs'][0]['id']
lyric_url = "http://music.163.com/api/song/media?id=" + str(song_id)
lyric = requests.get(lyric_url)
print(lyric.json()['lyric'])