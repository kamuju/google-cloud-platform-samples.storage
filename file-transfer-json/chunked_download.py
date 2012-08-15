# Copyright 2012 Google Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Downloads an object from Google Cloud Storage to a local file.

The file is downloaded in CHUNKSIZE pieces, and the process can resume in case
of certain failures.

Usage example:
  $ python chunked_download.py bucket_name/obj ~/Desktop/filename

"""

import random
import sys
import time

from apiclient.discovery import build as discovery_build
from apiclient.errors import HttpError
from apiclient.http import MediaIoBaseDownload
import httplib2
from oauth2client.client import OAuth2WebServerFlow
from oauth2client.file import Storage as CredentialStorage
from oauth2client.tools import run as run_oauth2

FLOW = OAuth2WebServerFlow(
    # NOTE: You will have to provide your own client ID and secret.
    # For more information, please visit:
    #   https://developers.google.com/accounts/docs/OAuth2
    client_id='',
    client_secret='',
    scope='https://www.googleapis.com/auth/devstorage.read_only')

# File where we will store authentication credentials.
CREDENTIALS_FILE = 'credentials.json'

# Retry transport and file IO errors.
RETRYABLE_ERRORS = (httplib2.HttpLib2Error, IOError)

# Number of bytes to download in each request.
CHUNKSIZE = 2 * 1024 * 1024


def HandleProgresslessIter(error, progressless_iters, num_retries):
  if progressless_iters > num_retries:
    print 'Failed to make progress for too many consecutive iterations.'
    raise error

  sleeptime = random.random() * (2**progressless_iters)
  print ('Caught exception (%s). Sleeping for %s seconds before retry #%d.'
         % (str(error), sleeptime, progressless_iters))
  time.sleep(sleeptime)


def Download(downloader, num_retries=5):
  progressless_iters = 0
  done = False
  while done is False:
    try:
      error = None
      progress, done = downloader.next_chunk()
      if progress:
        print 'Download %d%%.' % int(progress.progress() * 100)
    except HttpError, err:
      error = err
      if err.resp.status not in [500, 502, 503, 504]:
        raise
    except RETRYABLE_ERRORS, err:
      error = err

    if error is not None:
      progressless_iters += 1
      HandleProgresslessIter(error, progressless_iters, num_retries)
    else:
      progressless_iters = 0

  return True


def main(argv):
  bucket_name, object_name = argv[1].split('/', 1)
  filename = argv[2]

  print 'Authenticating...'
  credential_storage = CredentialStorage('credentials.json')
  credentials = credential_storage.get()
  if credentials is None or credentials.invalid:
    credentials = run_oauth2(FLOW, credential_storage)

  print 'Constructing Google Cloud Storage service...'
  http = credentials.authorize(httplib2.Http())
  service = discovery_build('storage', 'v1beta1', http=http)

  print 'Building downloader...'
  request = service.objects().get_media(bucket=bucket_name, object=object_name)
  f = file(filename, 'w')
  downloader = MediaIoBaseDownload(f, request, chunksize=CHUNKSIZE)

  print 'Downloading object: %s from bucket: %s to file: %s' % (object_name,
                                                                bucket_name,
                                                                filename)

  Download(downloader, http)
  print 'Download complete!'


if __name__ == '__main__':
  main(sys.argv)
