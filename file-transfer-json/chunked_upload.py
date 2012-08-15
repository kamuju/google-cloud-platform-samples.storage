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


"""Uploads a file to Google Cloud Storage.

The file is uploaded in CHUNKSIZE pieces, and the process can resume in case of
certain failures.

Usage example:
  $ python chunked_upload.py ~/Desktop/filename bucket_name/obj

"""

import random
import sys
import time

from apiclient.discovery import build as discovery_build
from apiclient.errors import HttpError
from apiclient.http import MediaFileUpload
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
    scope='https://www.googleapis.com/auth/devstorage.read_write')

# File where we will store authentication credentials.
CREDENTIALS_FILE = 'credentials.json'

# Retry transport and file IO errors.
RETRYABLE_ERRORS = (httplib2.HttpLib2Error, IOError)

# Mimetype to use if one can't be guessed from the file extension.
DEFAULT_MIMETYPE = 'application/octet-stream'

# Number of bytes to upload in each request.
CHUNKSIZE = 2 * 1024 * 1024


def HandleProgresslessIter(error, progressless_iters, num_retries):
  if progressless_iters > num_retries:
    print 'Failed to make progress for too many consecutive iterations.'
    raise error

  sleeptime = random.random() * (2**progressless_iters)
  print ('Caught exception (%s). Sleeping for %s seconds before retry #%d.'
         % (str(error), sleeptime, progressless_iters))
  time.sleep(sleeptime)


def Upload(request, num_retries=5):
  progressless_iters = 0
  response = None
  while response is None:
    try:
      error = None
      progress, response = request.next_chunk()
      if progress:
        print 'Upload %d%%' % (100 * progress.progress())
      progressless_iters = 0
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


def main(argv):
  filename = argv[1]
  bucket_name, object_name = argv[2].split('/', 1)

  print 'Authenticating...'
  credential_storage = CredentialStorage('credentials.json')
  credentials = credential_storage.get()
  if credentials is None or credentials.invalid:
    credentials = run_oauth2(FLOW, credential_storage)

  print 'Constructing Google Cloud Storage service...'
  http = credentials.authorize(httplib2.Http())
  service = discovery_build('storage', 'v1beta1', http=http)

  print 'Building upload request...'
  media = MediaFileUpload(filename, chunksize=CHUNKSIZE, resumable=True)
  if not media.mimetype():
    media = MediaFileUpload(filename, DEFAULT_MIMETYPE, resumable=True)
  request = service.objects().insert(bucket=bucket_name, name=object_name,
                                     media_body=media)

  print 'Uploading file: %s to object: %s in bucket: %s ' % (filename,
                                                             object_name,
                                                             bucket_name)
  Upload(request)
  print 'Upload complete!'


if __name__ == '__main__':
  main(sys.argv)
