#
# This script reads a list of web URLs from a remote JSON file
# and generates screenshots of the web page behind each URL
# in various resolutions.
#
# The result is stored to cloud storage as a file and to
# a Firestore DB for the metadata.
#
# Written for Python 3

import argparse
import requests
import logging
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import random
from datetime import datetime
from google.cloud import storage
from google.cloud import datastore


# URLs we have already covered in this run
urls_done = {}

tempdir = None

sizes = ([360, 640], [1500, 1500])

key_path = '/secrets/service-account.json'

bucket_name = "green-spider-screenshots.sendung.de"

storage_client = None
datastore_client = None
bucket = None


def get_urls():
    """
    Read URL list to create screenshots for, return
    as iterator in shuffled order.
    """
    url = "https://github.com/netzbegruenung/green-spider-webapp/raw/master/src/spider_result_compact.json"

    logging.info("Getting URL data from %s" % url)

    count = 0

    r = requests.get(url)
    items = r.json()

    # randomize order, to increase resilience
    random.seed()
    random.shuffle(items)

    for item in items:
        urls = item.get('resulting_urls')

        if urls is None or len(urls) == 0:
            continue

        url = urls[0]

        if url in urls_done:
            continue

        count += 1
        urls_done[url] = True
        
        yield url
    
    logging.info("Read %s URLs from source" % count)


def make_screenshot(url, width, height, loglevel):
    """
    Creates a screenshot for the URL in the given size
    and return a metadata record. Uploads the resulting
    image to a Google Cloud Storage bucket.
    """
    global tempdir
    global bucket

    size = [width, height]
    logging.info("Screenshotting URL %s size w=%s, h=%s" % (url, width, height))

    sizeargument = "%spx*%spx" % (size[0], size[1])

    # create path based on size and URL (MD5 hashed)
    filename = hashlib.md5(bytearray(url, 'utf-8')).hexdigest() + '.png'
    subfolder = "%sx%s" % (size[0], size[1])
    local_dir = '%s/%s' % (tempdir, subfolder)
    local_path = '%s/%s' % (local_dir, filename)

    os.makedirs(local_dir, exist_ok=True)

    command = ['/phantomjs/bin/phantomjs']
    if loglevel == 'debug':
        command.append('--debug=true')
        command.append('--webdriver-loglevel=DEBUG')
    command.append('/rasterize.js')
    command.append(url)
    command.append(local_path)
    command.append(sizeargument)
    subprocess.run(command)

    # Upload outcome
    blob = bucket.blob('%s/%s' % (subfolder, filename))
    if not os.path.exists(local_path):
        logging.warning("No screenshot created: size=%s, url='%s'" % (size, url))
    else:
        logging.debug("Uploading %s to %s/%s" % (local_path, subfolder, filename))
        with open(local_path, 'rb') as my_file:
            blob.upload_from_file(my_file, content_type="image/png")
            blob.make_public()
        os.remove(local_path)
            
        return {
            "url": url,
            "size": [width, height],
            "screenshot_url": "http://%s/%s/%s" % (bucket_name, subfolder, filename),
            "user_agent": "phantomjs-2.1.1",
            "created": datetime.utcnow(),
        }



def main():
    global storage_client
    global datastore_client
    global bucket
    global tempdir

    parser = argparse.ArgumentParser()
    parser.add_argument('--credentials-path', dest='credentials_path',
                        help='Path to the service account credentials JSON file',
                        default='/secrets/service-account.json')
    parser.add_argument('--loglevel', help="error, warn, info, or debug (default: info)", default='info')
    parser.add_argument('--url', dest='urls', help='URL(s) to create screenshots for', nargs='*')
    args = parser.parse_args()

    print(args)

    loglevel = args.loglevel.lower()
    if loglevel == 'error':
        logging.basicConfig(level=logging.ERROR)
    elif loglevel == 'warn':
        logging.basicConfig(level=logging.WARN)
    elif loglevel == 'debug':
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)
        loglevel = 'info'

    tempdir = tempfile.mkdtemp()

    storage_client = storage.Client.from_service_account_json(args.credentials_path)
    bucket = storage_client.get_bucket(bucket_name)

    datastore_client = datastore.Client.from_service_account_json(args.credentials_path)

    # properties to not include in indexes
    exclude_from_indexes = ['size', 'screenshot_url', 'user_agent', 'created']

    urls = args.urls
    if urls is None:
        urls = list(get_urls())

    for url in urls:
        
        for size in sizes:

            try:
                data = make_screenshot(url, size[0], size[1], loglevel)
                if data is not None:
                    logging.debug(data)
                    key = datastore_client.key('webscreenshot', data['screenshot_url'])
                    entity = datastore.Entity(key=key, exclude_from_indexes=exclude_from_indexes)
                    entity.update(data)
                    datastore_client.put(entity)
            except Exception as e:
                logging.warn("Error in %s: %s" % (url, e))
    
    shutil.rmtree(tempdir)


if __name__ == "__main__":
    main()
