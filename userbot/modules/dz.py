# MIT License

# Copyright (c) 2021 uh_wot

# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

"""Download music from Deezer"""
import os

from requests import get
from requests.models import HTTPError

from userbot import TEMP_DOWNLOAD_DIRECTORY
from userbot.events import register

from binascii import hexlify
from Cryptodome.Hash import MD5
from Cryptodome.Cipher import AES

CLIENT_ID = "119915"
CLIENT_SECRET = "2f5b4c9785ddc367975b83d90dc46f5c"

FORMATS = {
    "flac": "9",
    "320": "3",
    "128": "1",
}


class Error(Exception):
    """Base class for exceptions in this module."""

    pass


class APIError(Error):
    def __init__(self, type, message):
        self.type = type
        self.message = message


async def get_json(url):
    res = get(url)
    res.raise_for_status()
    res = res.json()

    try:
        error = res["error"]
        raise APIError(error["type"], error["message"])
    except KeyError:
        return res


async def track_url(md5_origin, format, id, media_version):
    # mashing a bunch of metadata and hashing it with MD5
    info = b"\xa4".join(
        [i.encode() for i in [md5_origin, format, str(id), str(media_version)]]
    )
    hash = MD5.new(info).hexdigest()

    # hash + metadata
    hash_metadata = hash.encode() + b"\xa4" + info + b"\xa4"

    # padding
    while len(hash_metadata) % 16 > 0:
        hash_metadata += b"\x00"

    # AES encryption in parts of 16
    aes_cipher = AES.new(b"jo6aey6haid2Teih", AES.MODE_ECB)
    result = hexlify(aes_cipher.encrypt(hash_metadata))

    # getting url
    return f"https://cdns-proxy-{md5_origin[0]}.dzcdn.net/api/1/{result.decode()}"


async def download_file(url, id):
    trk_path = os.path.join(TEMP_DOWNLOAD_DIRECTORY, f"{str(id)}.mp3")
    with get(url, stream=True) as r:
        size = r.headers["content-length"]
        r.raise_for_status()
        with open(trk_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
    return trk_path, size


@register(outgoing=True, pattern=r"\.dz (.*) (128|320|flac)")
async def dz(event):
    format_num = FORMATS[event.pattern_match.group(2)]
    track_id = event.pattern_match.group(1)

    await event.edit("**Getting track info...**")

    url = f"https://connect.deezer.com/oauth/access_token.php?grant_type=client_credentials&client_id={CLIENT_ID}&client_secret={CLIENT_SECRET}&output=json"
    try:
        token = (await get_json(url))["access_token"]
    except Exception as e:
        await event.edit(f"Error while getting access token:\n**{e}**")
        return

    url = f"https://api.deezer.com/track/{track_id}?access_token={token}"
    try:
        res = await get_json(url)
    except Exception as e:
        await event.edit(f"Error while getting track info:\n**{e}**")
        return

    await event.edit("**Downloading...**")

    md5_origin = res["md5_origin"]
    id = res["id"]
    if id < 0:  # user-uploaded track
        format_num = "0"
    media_version = res["media_version"]
    url = await track_url(md5_origin, format_num, id, media_version)

    try:
        trk_path, size = await download_file(url, id)
    except HTTPError:
        await event.edit("**Track unavailable.**")
        return

    await event.edit("**Uploading...**")

    await event.client.send_file(
        event.chat_id,
        trk_path,
        caption=f"**{res['artist']['name']} - {res['title']}**",
        file_size=int(size),
        supports_streaming=True,
    )

    await event.delete()

    os.remove(trk_path)
