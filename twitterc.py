#!/usr/bin/env python
# -*- coding: utf-8 -*-
# twitterc.py
# Copyright (C) 2017-2020 KunoiSayami
#
# This module is part of Twitter-Image-Auto-Downloader and is released under
# the AGPL v3 License: https://www.gnu.org/licenses/agpl-3.0.txt
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.
import asyncio
import concurrent.futures
import logging
import re
import signal
import traceback
from dataclasses import dataclass
from typing import Generator, List, Optional, Tuple

import aiofiles
import aiohttp
import aiohttp_socks
import pyperclip

photo = re.compile(r'^https:\/\/pbs\.twimg\.com\/media\/([a-zA-Z\d\-\_]+)\?format=(png|jpg)&name=.*$')
media = re.compile(r'^https:\/\/twitter.com\/i\/status/\d+$')
video = re.compile(
    r'(https:\/\/video.twimg.com\/(\w+|ext_tw)_video\/\d+(\/pu)?\/vid\/(\d+)x(\d+)\/([\w-]+\.mp4)\?tag=\d+)')
csrf = re.compile(r'name=\'csrfmiddlewaretoken\' value=\'(\w+)\'')


def download_ex(Session: aiohttp.ClientSession, url: str, filename: str):
    # url.replace('format=jpg', 'format=png')
    req = Session.get(url, stream=True)
    req.raise_for_status()
    with open(f'{filename}.png', 'wb') as fout:
        while (chunk := req.iter_content(chunk_size=1024)):
            fout.write(chunk)
    logging.info('%s.png download completed', filename)


b_run = True
download_queue: List[concurrent.futures.Future] = []


async def download(session: aiohttp.ClientSession, url: str, filename: str) -> None:
    i = 0
    async with session.get(url) as req:
        print(f'Downloading {filename}', end='')
        async with aiofiles.open(filename, 'wb') as fout:
            while chunk := await req.content.read(102400):
                i += 100
                print(f'\rDownloading {filename} {i}k', end='')
                await fout.write(chunk)
    print('\r', end='')
    logging.info('Download %s completed', filename)


@dataclass(init=False)
class Media:
    url: str
    d1: int
    d2: int
    file_name: str

    def __init__(self, obj: Tuple[str, str, str, str]):
        self.url = obj[0]
        self.d1 = int(obj[3])
        self.d2 = int(obj[4])
        self.file_name = obj[5]

    def best(self, o: Optional['Media']) -> 'Media':
        if o is None:
            return self
        if self.d1 * self.d2 > o.d1 * o.d2:
            return self
        else:
            return o


async def get_media_info(session: aiohttp.ClientSession, csrfmiddlewaretoken: str, url: str) -> Generator[
    Media, None, None]:
    async with session.post('https://twittervideodownloader.com/download',
                            data={'csrfmiddlewaretoken': csrfmiddlewaretoken, 'tweet': url},
                            headers={
                                'Origin': 'https://twittervideodownloader.com',
                                'Referer': 'https://twittervideodownloader.com/error',
                                'user-agent':
                                    'Mozilla/5.0 (Windows NT 6.3; Win64; x64) AppleWebKit/537.36'
                                    '(KHTML, like Gecko) Chrome/81.0.4729.90 Safari/527.56'
                            }) as req:
        for x in video.findall(await req.text()):
            yield Media(x)


async def download_media(session: aiohttp.ClientSession, url: str) -> None:
    session.cookie_jar.clear()
    csrfmiddlewaretoken = ''
    # cookie = ''
    async with session.get('https://twittervideodownloader.com/') as req:
        csrfmiddlewaretoken = csrf.search(await req.text()).group(1)
    # cookie = req.cookies.get('csrftoken').value
    real_media = None
    async for x in get_media_info(session, csrfmiddlewaretoken, url):
        real_media = x.best(real_media)
    # print(real_media)
    # print(real_media)
    await download(session, real_media.url, real_media.file_name)


async def watch_clip(queue: asyncio.Queue) -> None:
    last = ''
    while b_run:
        await asyncio.sleep(.01)
        s = pyperclip.paste()
        if last == s:
            continue
        queue.put_nowait(s)
        last = s


enable_proxy = False
socks5_proxy = 'socks5://127.0.0.1:1080/'


async def main():
    queue = asyncio.Queue()
    future = asyncio.run_coroutine_threadsafe(watch_clip(queue), asyncio.get_event_loop())
    connector = aiohttp_socks.SocksConnector.from_url(socks5_proxy) if enable_proxy else None
    async with aiohttp.ClientSession(connector=connector, headers={'user-agent':
                                                                       'Mozilla/5.0 (Windows NT 6.3; Win64; x64) '
                                                                       'AppleWebKit/537.36 '
                                                                       '(KHTML, like Gecko) Chrome/81.0.4729.90 '
                                                                       'Safari/527.56'},
                                     raise_for_status=True) as session:
        task = asyncio.create_task(queue.get())
        while b_run:
            done, _pending = await asyncio.wait([task], timeout=.5)
            if len(done):
                done = done.pop().result()
                r1 = photo.match(done)  # type: ignore
                r2 = media.match(done)  # type: ignore
                try:
                    if r1 or r2:
                        for retries in range(3):
                            try:
                                if r1:
                                    await download(session, ''.join((done.split('?format=jpg')[0], '?format=jpg')),
                                                   f'{r1.group(1)}.png')  # type: ignore
                                else:
                                    await download_media(session, done)  # type: ignore
                                break
                            except aiohttp.client_exceptions.ClientError:
                                logging.exception('Got exception, retry connect (%d).', retries)
                                if retries == 3:
                                    raise
                except:
                    traceback.print_exc()
                task = asyncio.create_task(queue.get())
            if not b_run:
                break
        task.cancel()
    future.cancel()


def handle(*_args) -> None:
    global b_run
    b_run = False


if __name__ == "__main__":
    # coloredlogs.install(logging.INFO, fmt='%(asctime)s,%(msecs)03d %(asctime)s - %(levelname)s - %(name)s - %(funcName)s - %(lineno)d - %(message)s')
    signal.signal(2, handle)
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s - %(levelname)s - %(name)s - %(funcName)s - %(lineno)d - %(message)s')
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
    loop.run_until_complete(asyncio.sleep(.25))
    loop.close()
