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

"""IP lookup using ip-api.com"""
from re import sub
from requests import get

from userbot import CMD_HELP
from userbot.events import register


@register(outgoing=True, pattern=r"^\.ip")
async def ip(args):
    try:
        ip = args.text.split()[1]
    except IndexError:
        ip = ""

    lookup = get(f"http://ip-api.com/json/{ip}").json()
    fixed_lookup = {}

    for key, value in lookup.items():
        special = {
            "lat": "Latitude",
            "lon": "Longitude",
            "isp": "ISP",
            "as": "AS",
            "asname": "AS name",
        }
        if key in special:
            fixed_lookup[special[key]] = str(value)
            continue

        key = sub(r"([a-z])([A-Z])", r"\g<1> \g<2>", key)
        key = key.capitalize()

        if not value:
            value = "None"

        fixed_lookup[key] = str(value)

    text = ""

    for key, value in fixed_lookup.items():
        text = text + f"**{key}:** `{value}`\n"

    await args.edit(text)


CMD_HELP.update(
    {
        "ip": ">`.ip <ip/domain>[optional]`"
        "\nUsage: Looks up IP address. If IP isn't specified, looks up the userbot's IP."
    }
)
