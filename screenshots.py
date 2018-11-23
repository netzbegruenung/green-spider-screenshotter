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

bucket_name = "green-spider-screenshots.sendung.de"

spider_results_kind = 'spider-results'

storage_client = None
datastore_client = None
bucket = None


def get_urls(client):
    """
    Read URL list to create screenshots for, return
    as iterator in shuffled order.
    """
    logging.info("Getting URL data")

    query = client.query(kind=spider_results_kind)

    count = 0
    items = []
    for entity in query.fetch(eventual=True):
        items.append(entity)

    # randomize order, to increase resilience
    random.seed()
    random.shuffle(items)

    for item in items:
        logging.debug("Importing resulting URL(s) from %s" % item.key.name)
        checks = item.get('checks')
        
        if checks is None:
            continue

        urls = checks.get('url_canonicalization')
        if urls is None or len(urls) == 0:
            logging.debug("No URL for %s" % item.key.name)
            continue

        url = urls[0]

        if url in urls_done:
            logging.debug("URL %s is already marked as done. Skipping." % url)
            continue
        
        logging.debug("Selecting URL for site '%s': %s" % (item.key.name, url))

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
    parser.add_argument('--storage-credentials-path',
                        dest='storage_credentials_path',
                        help='Path to the cloud storage service account credentials JSON file',
                        default='/secrets/screenshots-uploader.json')
    parser.add_argument('--datastore-credentials-path',
                        dest='datastore_credentials_path',
                        help='Path to the datastore service account credentials JSON file',
                        default='/secrets/datastore-writer.json')
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

    storage_client = storage.Client.from_service_account_json(args.storage_credentials_path)
    bucket = storage_client.get_bucket(bucket_name)

    datastore_client = datastore.Client.from_service_account_json(args.datastore_credentials_path)

    # properties to not include in indexes
    exclude_from_indexes = ['size', 'screenshot_url', 'user_agent', 'created']

    urls = args.urls
    if urls is None:
        urls = list(get_urls(datastore_client))

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
