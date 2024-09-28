import asyncio
import aiohttp
import aiofiles
import urllib
import json
import time
import os
import subprocess
import requests
import re
from datetime import datetime, timedelta
from bs4 import BeautifulSoup

WC_FILE = 'wc.json'
DATA_FILE = 'img/data.json'
MAX_IMAGES = 30

SMARTYPLANET_URLS = {
    # https://aneto.smartyplanet.com/es/public/show/1830
    #'pico-aneto': 'https://aneto.smartyplanet.com/public/estacio/ajax/1830',
    #'glaciar-aneto': 'https://bielsa-aragnouet.smartyplanet.com/public/estacio/ajax/1632',
    # https://bielsa-aragnouet.smartyplanet.com/es/public/show/1454
    'bielsa-boca-sud': 'https://bielsa-aragnouet.smartyplanet.com/public/estacio/ajax/1454'
}

# get month (1-12) with 0 padding (01,02,...,12)
def get_month():
    return str(datetime.now().month).zfill(2)

def get_year():
    return str(datetime.now().year)

ARANTEC_URLS = {
    'pico-aneto': f'https://arantec-ftp.s3.eu-west-2.amazonaws.com/?delimiter=cameras/005044&fetch-owner=false&list-type=2&prefix=cameras/005044/{get_year()}{get_month()}',
    'glaciar-aneto': f'https://arantec-ftp.s3.eu-west-2.amazonaws.com/?delimiter=cameras/005011&fetch-owner=false&list-type=2&prefix=cameras/005011/{get_year()}{get_month()}'
}

ARANTEC_WCS = list(ARANTEC_URLS.keys())

SMARTYPLANET_URL_TEMPLATE = 'https://s3-eu-west-2.amazonaws.com/smartyplanet-webcam-storage/{pic_partial_url}'
SMARTYPLANET_WCS = list(SMARTYPLANET_URLS.keys())

VIEWSURF_URLS = {
    'porte-le-village': 'https://www.viewsurf.com/univers/montagne/vue/17356-france-languedoc-roussillon-porte-puymorens-depart-telesiege-estagnol',
    'porte-la-vignole': 'https://www.viewsurf.com/univers/montagne/vue/18848-france-languedoc-roussillon-porte-puymorens-la-vignole',
    'porte-estanyol': 'https://www.viewsurf.com/univers/montagne/vue/17354-france-languedoc-roussillon-porte-puymorens-arrivee-telesiege-estagnol',
    'cambre-dase': 'https://www.viewsurf.com/univers/montagne/vue/16542-france-languedoc-roussillon-saint-pierre-dels-forcats-montagne',
    'formigueres-estacio': 'https://www.viewsurf.com/univers/montagne/vue/14628-france-languedoc-roussillon-formigueres-la-station',
    'les-angles-roc-daude': 'https://www.viewsurf.com/univers/montagne/vue/15734-france-languedoc-roussillon-les-angles-roc-daude',
    'les-angles-pla-mir': 'https://www.viewsurf.com/univers/montagne/vue/15738-france-languedoc-roussillon-les-angles-arrivee-pla-del-mir',
    'bulloses': 'https://www.viewsurf.com/univers/plage/vue/12756-france-languedoc-roussillon-les-angles-le-lac-des-bouillouses',
    'mijanes-pistes': 'https://viewsurf.com/univers/montagne/vue/17728-france-midi-pyrenees-mijanes-les-pistes',
    'circ-gavarnie': 'https://www.viewsurf.com/univers/montagne/vue/12310-france-midi-pyrenees-gavarnie-cirque-de-gavarnie',
    'saint-andre-gavarnie': 'https://www.viewsurf.com/univers/montagne/vue/12810-france-midi-pyrenees-gavarnie-pic-de-saint-andre',
    'font-romeu-snowpark': 'https://www.viewsurf.com/univers/montagne/vue/15726-france-languedoc-roussillon-font-romeu-odeillo-via-snowpark'
}

VIEWSURF_WCS = list(VIEWSURF_URLS.keys())

VIEWSURF_URL_TEMPLATE = 'https://deliverys4.joada.net/contents/encodings/vod/{uuid}/poster.jpg'

CLIMAYNIEVEPIRINEOS_WCS = [
    'baqueira-poble',
    'bordes-envalira',
    'portalet-nord'
]

CLIMAYNIEVEPIRINEOS_TOKEN = ''

def get_climaynievepirineos_token():
    global CLIMAYNIEVEPIRINEOS_TOKEN
    res = requests.get('https://www.climaynievepirineos.com/webcams/')
    if res.status_code == 200:
        # Find using regex the following pattern: cam.jpg?wck=md5_token
        d = re.search(r'cam\.jpg\?wck=(\w+)', res.text)
        if d:
            token = d.group().split('=')[-1]
            CLIMAYNIEVEPIRINEOS_TOKEN = token
            print(f"Climaynievepirineos token: {token}")
        else:
            print("Climaynievepirineos token not found")
            return None
    else:
        print(f"Error getting climaynievepirineos token: {res.status_code}")
    return None

async def fetch_arantec(session, wc, data):
    try:
        url = ARANTEC_URLS[wc['name']]
        pic_url = ""
        async with session.get(url) as resp:
            resp_data = await resp.read()
            if resp.status == 200 and len(resp_data) > 0:
                """
                <ListBucketResult>
                <Name>arantec-ftp</Name>
                <Prefix>cameras/005044/2024090</Prefix>
                <KeyCount>56</KeyCount>
                <MaxKeys>1000</MaxKeys>
                <Delimiter>cameras/005044</Delimiter>
                <IsTruncated>false</IsTruncated>
                <Contents>
                <Key>cameras/005044/20240901000537.jpg</Key>
                <LastModified>2024-09-01T00:18:35.000Z</LastModified>
                <ETag>"86651caa825acb883063677ff6c33a51"</ETag>
                <Size>68090</Size>
                <StorageClass>STANDARD</StorageClass>
                </Contents>
                ...
                </ListBucketResult>
                """
                soup = BeautifulSoup(resp_data, 'html.parser')
                contents = soup.find_all('contents')

                datestr = contents[-1].key.text.split('/')[-1].split('.')[0]
                date = datetime.strptime(datestr, '%Y%m%d%H%M%S')
                now = datetime.utcnow()
                if (date + timedelta(minutes=35)) < now:
                    # Pic is older than 30 minutes
                    print(f"ARANTEC picture is too old! Skipping (curr_time={now}, wc_time={date})")
                    return

                pic_url = f'https://arantec-ftp.s3.eu-west-2.amazonaws.com/{contents[-1].key.text}'

    except Exception as e:
        print('ERROR ARANTEC 1', e)
        return

    print(f"ARANTEC pic for {wc['name']}: {pic_url}")

    try:
        async with session.get(pic_url) as pic_resp:
            ext = pic_url.split('.')[-1]
            resp_data = await pic_resp.read()
            now = time.time()
            if pic_resp.status == 200 and len(resp_data) > 0:
                img_path = f'img/{wc["name"]}-{str(int(now))}.{ext}'
                print(f"Downloading {wc['name']} ({img_path})")
                if ext == 'php':
                    ext = 'jpg'
                f = await aiofiles.open('img/{}-{}.{}'.format(wc['name'], str(int(now)), ext), mode='wb')
                add_pic(data, wc, img_path, int(now))
                await f.write(resp_data)
                await f.close()
            else:
                print(f"Error getting viewsurf image {pic_url}")
    except Exception as e:
        print('ERROR ARANTEC 2', e)
        return

async def fetch_smartyplanet(session, wc, data):
    url = SMARTYPLANET_URLS[wc['name']]
    pic_url = ""
    good = True
    async with session.get(url) as resp:
        resp_data = await resp.read()
        if resp.status == 200 and len(resp_data) > 0:
            r = json.loads(resp_data)
            try:
                estat = r['estat_estacio']
                if estat == 0:
                    good = False
                else:
                    try:
                        date = datetime.strptime(r['dataDada'], '%Y-%m-%d %H:%M')
                        now = datetime.now()
                        if (date + timedelta(minutes=35)) < now:
                            # Pic is older than 30 minutes
                            print("Smartyplanet picture is too old! Skipping")
                            return
                    except Exception as e:
                        print('Error', e)
                    pic_url = SMARTYPLANET_URL_TEMPLATE.format(pic_partial_url=r['url_img'])
            except Exception as e:
                print('Error', e)
                return

    if not good:
        print(f'Camera {wc["name"]} not working')
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
                if ext == 'php':
                    ext = 'jpg'
                f = await aiofiles.open('img/{}-{}.{}'.format(wc['name'], str(int(now)), ext), mode='wb')
                add_pic(data, wc, img_path, int(now))
                await f.write(resp_data)
                await f.close()
            else:
                print(f"Error getting smartyplanet image {pic_url}")
    except Exception as e:
        print(e)

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
                if ext == 'php':
                    ext = 'jpg'
                f = await aiofiles.open('img/{}-{}.{}'.format(wc['name'], str(int(now)), ext), mode='wb')
                add_pic(data, wc, img_path, int(now))
                await f.write(resp_data)
                await f.close()
            else:
                print(f"Error getting viewsurf image {pic_url}")
    except Exception as e:
        print(e)

def is_climaynievepirineos_webcam(name):
    return name in CLIMAYNIEVEPIRINEOS_WCS

def is_viewsurf_webcam(name):
    return name in VIEWSURF_WCS

def is_smartyplanet_webcam(name):
    return name in SMARTYPLANET_WCS

def is_arantec_webcam(name):
    return name in ARANTEC_WCS

def add_pic(data, wc, pic_path, t):
    target_element_idx = None
    for idx, elem in enumerate(data):
        if elem['name'] == wc['name']:
            target_element_idx = idx
            break

    if target_element_idx is None:
        print(f"Adding new webcam {wc['name']}")
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

    if wc['original_name'] != data[target_element_idx]['original_name']:
        data[target_element_idx]['original_name'] = wc['original_name']
    if wc['lat'] != data[target_element_idx]['lat']:
        data[target_element_idx]['lat'] = wc['lat']
    if wc['lon'] != data[target_element_idx]['lon']:
        data[target_element_idx]['lon'] = wc['lon']
    if wc['attribution'] != data[target_element_idx]['attribution']:
        data[target_element_idx]['attribution'] = wc['attribution']
    if 'related' in wc.keys():
        data[target_element_idx]['related'] = wc['related']


async def fetch(session, wc, data):
    url = wc['url']
    ext = url.split('.')[-1]
    if '?' in url:
        tmp_url = ''.join(url.split('?')[:-1])
        ext = tmp_url.split('.')[-1]
    if is_viewsurf_webcam(wc['name']):
        await fetch_viewsurf(session, wc, data)
    elif is_smartyplanet_webcam(wc['name']):
        await fetch_smartyplanet(session, wc, data)
    elif is_arantec_webcam(wc['name']):
        await fetch_arantec(session, wc, data)
    else:
        if is_climaynievepirineos_webcam(wc['name']):
            url = url + f'?wck={CLIMAYNIEVEPIRINEOS_TOKEN}'
            print(f"Fetching climaynievepirineos webcam {wc['name']}: {url}")
        async with session.get(url) as resp:
            now = time.time()
            resp_data = await resp.read()
            if resp.status == 200 and len(resp_data) > 0:
                if ext == 'php':
                    ext = 'jpg'
                print(f"Downloading {wc['name']}")
                img_path = f'img/{wc["name"]}-{str(int(now))}.{ext}'
                f = await aiofiles.open('img/{}-{}.{}'.format(wc['name'], str(int(now)), ext), mode='wb')
                add_pic(data, wc, img_path, int(now))
                await f.write(resp_data)
                await f.close()
            else:
                print(f'Error {resp.status} when fetching WC {wc["name"]}')

async def get_data(content, data):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/86.0.2531.3072 Safari/537.36',
        'Referer': 'https://www.alberguesyrefugios.com/'
    }
    async with aiohttp.ClientSession(headers=headers) as session:
        results = await asyncio.gather(*[fetch(session, wc, data) for wc in content], return_exceptions=True)


get_climaynievepirineos_token()

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
            curr_path = os.getcwd()
            pic_path = wc['imgs'][-1]['path']
            pic_path_webp = '.'.join(pic_path.split('.')[:-1]) + '.webp'
            ext = pic_path.split('.')[-1]
            if wc['name'] in ["aneto-montarto", "parking-beret", "grandvalira-pas-de-la-casa", "grandvalira-grau-roig", "arcalis-cap-coma", "boi-taull", "arinsal", "ordino-base-coma", "soldeu-espiolets"]:
                # convert "$X" -scale 25% -size 25% -strip -quality 90 "${X}_converted" && mv "${X}_converted" "$X"
                subprocess.run(f'convert {curr_path}/{pic_path} -scale 25% -size 25% -strip {curr_path}/{pic_path}_converted'.split(" "))
                subprocess.run(f'mv {curr_path}/{pic_path}_converted {curr_path}/{pic_path}'.split(" "))
                #os.system(f'convert "{pic_path}" -scale 25% -size 25% -strip -quality 90 "{pic_path}_converted"')
                #os.system(f'mv "{pic_path}_converted {pic_path}"')

            # Make all images 700px wide to save space and strip metadata
            if ext == 'jpg' or ext == 'jpeg':
                subprocess.run(f'convert {curr_path}/{pic_path} -resize 700 -strip {curr_path}/{pic_path}'.split(" "))
            elif ext == 'png':
                subprocess.run(f'convert {curr_path}/{pic_path} -resize 700 -strip -quality 90 {curr_path}/{pic_path}'.split(" "))
            else:
                print(f"Unknown extension {ext} (file {pic_path})")

            if ext != 'webp':
                res = subprocess.run(f'cwebp -q 80 {curr_path}/{pic_path} -o {curr_path}/{pic_path_webp}'.split(" "))
                if res.returncode == 0:
                    subprocess.run(f'rm {curr_path}/{pic_path}'.split(" "))
                    pic_path = wc['imgs'][-1]['path'] = pic_path_webp

        with open(DATA_FILE, 'w') as f_data:
            f_data.write(json.dumps(data))
