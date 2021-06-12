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
from time import time

from requests import get
from requests.models import HTTPError
from telethon.tl.types import DocumentAttributeAudio

from userbot import TEMP_DOWNLOAD_DIRECTORY
from userbot.events import register

from binascii import hexlify
from Crypto.Hash import MD5
from Crypto.Cipher import AES

API = "https://api.deezer.com/"

CLIENT_ID = "119915"
CLIENT_SECRET = "2f5b4c9785ddc367975b83d90dc46f5c"

TOKEN_URL = f"https://connect.deezer.com/oauth/access_token.php?grant_type=client_credentials&client_id={CLIENT_ID}&client_secret={CLIENT_SECRET}&output=json"

FORMATS = {
    "flac": "9",
    "320": "3",
    "128": "1",
    "misc": "0",
}


class Error(Exception):
    """Base class for exceptions in this module."""

    pass


class APIError(Error):
    def __init__(self, type, message):
        self.type = type
        self.message = message


async def get_json(url):
    resp = get(url)
    resp.raise_for_status()
    resp = resp.json()

    try:
        error = resp["error"]
        raise APIError(error["type"], error["message"])
    except KeyError:
        return resp


async def get_access_token():
    try:
        from userbot.modules.sql_helper.globals import gvarstatus, addgvar
    except AttributeError:  # sql disabled
        return (await get_json(TOKEN_URL))["access_token"]

    token = gvarstatus("dz_token")
    expiry = gvarstatus("dz_token_expiry")
    if not token or not expiry or float(expiry) <= time():
        # getting new token from deezer and caching
        resp = await get_json(TOKEN_URL)
        token = resp["access_token"]
        expiry = time() + int(resp["expires"])
        addgvar("dz_token", token)
        addgvar("dz_token_expiry", expiry)

    return token


async def api_call(path):
    url = API + path + f"?access_token={await get_access_token()}"
    return await get_json(url)


async def track_url(md5_origin, format_num, id, media_version):
    # mashing a bunch of metadata and hashing it with MD5
    info = b"\xa4".join(
        [i.encode() for i in [md5_origin, format_num, str(id), str(media_version)]]
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


async def download_file(url, id, format):
    ext = "mp3"
    if format == "flac":
        ext = "flac"

    trk_path = os.path.join(TEMP_DOWNLOAD_DIRECTORY, f"{str(id)}_{format}.{ext}")
    with get(url, stream=True) as r:
        r.raise_for_status()
        with open(trk_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
    return trk_path


@register(outgoing=True, pattern=r"\.dz (.*) (misc|128|320|flac)")
async def dz(event):
    try:
        id = int(event.pattern_match.group(1))
    except ValueError:
        await event.edit("**Invalid track ID.**")
        return

    await event.edit("**Getting track info...**")

    api_path = f"track/{id}"
    try:
        resp = await api_call(api_path)
    except Exception as e:
        await event.edit(f"Error while getting track info:\n**{e}**")
        return

    id = resp["id"]
    if id < 0:  # user-uploaded track
        format = "misc"
    else:
        format = event.pattern_match.group(2)

    filesize = resp["filesize_" + format]
    if filesize in ["0", ""]:
        await event.edit("**Format unavailable.**")
        return
    format_num = FORMATS[format]

    await event.edit("**Downloading...**")

    md5_origin = resp["md5_origin"]
    media_version = resp["media_version"]
    url = await track_url(md5_origin, format_num, id, media_version)

    try:
        trk_path = await download_file(url, id, format)
    except HTTPError:
        await event.edit("**Track unavailable.**")
        return

    await event.edit("**Uploading...**")

    attributes = [
        DocumentAttributeAudio(
            duration=resp["duration"],
            voice=False,
            title=resp["title"],
            performer=resp["artist"]["name"],
            waveform=None,
        )
    ]

    cover = None
    md5_image = resp["md5_image"]
    if md5_image != "":
        url = f"https://cdns-images.dzcdn.net/images/cover/{md5_image}/320x320-000000-80-0-0.jpg"
        cover = get(url)
        try:
            cover.raise_for_status()
        except HTTPError:
            await event.edit("**Error while getting cover.**")
            return
        cover = cover.content

    await event.client.send_file(
        event.chat_id,
        trk_path,
        file_size=int(filesize),
        attributes=attributes,
        thumb=cover,
        supports_streaming=True,
    )

    await event.delete()

    os.remove(trk_path)
