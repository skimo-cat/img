import asyncio
import aiohttp
import aiofiles
import urllib
import json
import time
import os
import subprocess
from bs4 import BeautifulSoup

WC_FILE = 'wc.json'
DATA_FILE = 'img/data.json'
MAX_IMAGES = 30


VIEWSURF_URLS = {
    'porte-le-village': 'https://www.viewsurf.com/univers/montagne/vue/17356-france-languedoc-roussillon-porte-puymorens-depart-telesiege-estagnol',
    'porte-la-vignole': 'https://www.viewsurf.com/univers/montagne/vue/18848-france-languedoc-roussillon-porte-puymorens-la-vignole',
    'porte-estanyol': 'https://www.viewsurf.com/univers/montagne/vue/17354-france-languedoc-roussillon-porte-puymorens-arrivee-telesiege-estagnol',
    'cambre-dase': 'https://www.viewsurf.com/univers/montagne/vue/16542-france-languedoc-roussillon-saint-pierre-dels-forcats-montagne',
    'formigueres-estacio': 'https://www.viewsurf.com/univers/montagne/vue/14628-france-languedoc-roussillon-formigueres-la-station',
    'les-angles-roc-daude': 'https://www.viewsurf.com/univers/montagne/vue/15734-france-languedoc-roussillon-les-angles-roc-daude',
    'bulloses': 'https://www.viewsurf.com/univers/plage/vue/12756-france-languedoc-roussillon-les-angles-le-lac-des-bouillouses',
    'mijanes-pistes': 'https://viewsurf.com/univers/montagne/vue/17728-france-midi-pyrenees-mijanes-les-pistes'
}

VIEWSURF_WCS = list(VIEWSURF_URLS.keys())

VIEWSURF_URL_TEMPLATE = 'https://deliverys4.joada.net/contents/encodings/vod/{uuid}/poster.jpg'

async def fetch_viewsurf(session, wc, data):
    url = VIEWSURF_URLS[wc['name']]
    pic_url = ""
    async with session.get(url) as resp:
        resp_data = await resp.read()
        if resp.status == 200 and len(resp_data) > 0:
            soup = BeautifulSoup(resp_data, 'html.parser')
            iframe = soup.find('iframe')
            try:
                uuid = urllib.parse.parse_qs(urllib.parse.urlsplit(iframe['src']).query)['uuid'][0]
                pic_url = VIEWSURF_URL_TEMPLATE.format(uuid=uuid)
            except Exception as e:
                print(e)
                return

    try:
        async with session.get(pic_url) as pic_resp:
            if '?' in pic_url:
                pic_url = ''.join(pic_url.split('?')[:-1])
            ext = pic_url.split('.')[-1]
            resp_data = await pic_resp.read()
            now = time.time()
            if pic_resp.status == 200 and len(resp_data) > 0:
                img_path = f'img/{wc["name"]}-{str(int(now))}.{ext}'
                print(f"Downloading {wc['name']} ({img_path})")
                f = await aiofiles.open('img/{}-{}.{}'.format(wc['name'], str(int(now)), ext), mode='wb')
                add_pic(data, wc, img_path, int(now))
                await f.write(resp_data)
                await f.close()
            else:
                print(f"Error getting viewsurf image {pic_url}")
    except Exception as e:
        print(e)

def is_viewsurf_webcam(name):
    return name in VIEWSURF_WCS

def add_pic(data, wc, pic_path, t):
    target_element_idx = None
    for idx, elem in enumerate(data):
        if elem['name'] == wc['name']:
            target_element_idx = idx
            break

    if target_element_idx is None:
        data.append({'name': wc['name'],
                     'lat': wc['lat'],
                     'lon': wc['lon'],
                     'original_name': wc['original_name'],
                     'attribution': wc['attribution'],
                     'imgs': []})
        target_element_idx = len(data) - 1

    if len(data[target_element_idx]['imgs']) >= MAX_IMAGES:
        removed_elem = data[target_element_idx]['imgs'].pop(0)
        if os.path.isfile(removed_elem['path']):
            os.remove(removed_elem['path'])

    data[target_element_idx]['imgs'].append({'path': pic_path, 'timestamp': t})


async def fetch(session, wc, data):
    url = wc['url']
    if '?' in url:
        url = ''.join(url.split('?')[:-1])
    ext = url.split('.')[-1]
    if is_viewsurf_webcam(wc['name']):
        await fetch_viewsurf(session, wc, data)
    else:
        async with session.get(url) as resp:
            now = time.time()
            resp_data = await resp.read()
            if resp.status == 200 and len(resp_data) > 0:
                print(f"Downloading {wc['name']}")
                img_path = f'img/{wc["name"]}-{str(int(now))}.{ext}'
                f = await aiofiles.open('img/{}-{}.{}'.format(wc['name'], str(int(now)), ext), mode='wb')
                add_pic(data, wc, img_path, int(now))
                await f.write(resp_data)
                await f.close()

async def get_data(content, data):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/86.0.2531.3072 Safari/537.36',
        'Referer': 'https://www.alberguesyrefugios.com/'
    }
    async with aiohttp.ClientSession(headers=headers) as session:
        results = await asyncio.gather(*[fetch(session, wc, data) for wc in content], return_exceptions=True)

with open(WC_FILE, 'r') as f:
    content = json.loads(f.read())
    with open(DATA_FILE, 'r') as f_data:
        try:
            data = json.loads(f_data.read())
        except:
            data = []

        # Get data concurrently
        loop = asyncio.get_event_loop()
        loop.run_until_complete(get_data(content, data))


        for wc in data:
            if wc['name'] in ["grandvalira-pas-de-la-casa", "grandvalira-grau-roig", "arcalis-cap-coma", "boi-taull"]:
                pic_path = wc['imgs'][-1]['path']
                curr_path = os.getcwd()
                # convert "$X" -scale 25% -size 25% -strip -quality 90 "${X}_converted" && mv "${X}_converted" "$X"
                subprocess.run(f'convert {curr_path}/{pic_path} -scale 25% -size 25% -strip -quality 90 {curr_path}/{pic_path}_converted'.split(" "))
                subprocess.run(f'mv {curr_path}/{pic_path}_converted {curr_path}/{pic_path}'.split(" "))
                #os.system(f'convert "{pic_path}" -scale 25% -size 25% -strip -quality 90 "{pic_path}_converted"')
                #os.system(f'mv "{pic_path}_converted {pic_path}"')

        with open(DATA_FILE, 'w') as f_data:
            f_data.write(json.dumps(data))
