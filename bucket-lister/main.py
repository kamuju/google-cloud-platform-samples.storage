#!/usr/bin/env python
#
# Copyright 2012 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

"""Present formatted listings for Google Cloud Storage buckets.

This Google App Engine application takes a bucket name in the URL path and uses
the Google Cloud Storage JSON API and Google's Python client library to list the
bucket's contents.

For example, if this app is invoked with the URI
http://bucket-list.appspot.com/foo, it would extract the bucket name 'foo' and
issue a request to GCS for its contents. The app formats the listing into an XML
document, which is prepended with a reference to an XSLT style sheet for human
readable presentation.

For more information:

Google APIs Client Library for Python:
  <https://code.google.com/p/google-api-python-client/>
Google Cloud Storage JSON API:
  <https://developers.google.com/storage/docs/json_api/>
Using OAuth 2.0 for Server to Server Applications:
  <https://developers.google.com/accounts/docs/OAuth2ServiceAccount>
App Identity Python API Overview:
  <https://code.google.com/appengine/docs/python/appidentity/overview.html>
"""

from apiclient.discovery import build as build_service
import httplib2
from oauth2client.client import OAuth2WebServerFlow
from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import login_required
from google.appengine.ext.webapp.util import run_wsgi_app

# NOTE: You must provide a client ID and secret with access to the GCS JSON API.
# You can acquire a client ID and secret from the Google Developers Console.
#   <code.google.com/apis/console>
CLIENT_ID = ''
CLIENT_SECRET = ''
SCOPE = 'https://www.googleapis.com/auth/devstorage.read_only'
USER_AGENT = 'app-engine-bucket-lister'


# Since we don't plan to use all object attributes, we pass a fields argument to
# specify what the server should return.
FIELDS = 'items(name,media(timeCreated,hash,length))'


def JsonObjToXml(obj):
  """Convert a JSON object description into an XML string fields."""
  media = obj['media']
  return (('<Contents>'
           '<Key>%s</Key>'
           '<LastModified>%s</LastModified>'
           '<MD5>%s</MD5>'
           '<Size>%s</Size>'
           '</Contents>')
          % (obj['name'], media['timeCreated'], media['hash'], media['length']))


def JsonListingToXml(bucket, json_listing):
  """Convert the JSON listing to an XML string with the desired fields."""
  object_list_xml = ''.join([JsonObjToXml(obj)
                             for obj in json_listing['items']])
  return (('<?xml version=\'1.0\' encoding=\'UTF-8\'?>'
           '<?xml-stylesheet href="/listing.xsl" type="text/xsl"?>'
           '<ListBucketResult xmlns=\'http://doc.s3.amazonaws.com/2006-03-01\'>'
           '<Name>%s</Name>%s</ListBucketResult>') % (bucket, object_list_xml))


def GetBucketName(path):
  bucket = path[1:]  # Trim the preceding slash
  if bucket[-1] == '/':
    # Trim final slash, if necessary.
    bucket = bucket[:-1]
  return bucket


class MainHandler(webapp.RequestHandler):

  @login_required
  def get(self):
    callback = self.request.host_url + '/oauth2callback'
    flow = OAuth2WebServerFlow(client_id=CLIENT_ID,
                               client_secret=CLIENT_SECRET,
                               redirect_uri=callback,
                               access_type='online',
                               scope=SCOPE,
                               user_agent=USER_AGENT)

    bucket = GetBucketName(self.request.path)
    step2_url = flow.step1_get_authorize_url()
    # Add state to remember which bucket to list.
    self.redirect(step2_url + '&state=%s' % bucket)


class AuthHandler(webapp.RequestHandler):

  @login_required
  def get(self):
    callback = self.request.host_url + '/oauth2callback'
    flow = OAuth2WebServerFlow(client_id=CLIENT_ID,
                               client_secret=CLIENT_SECRET,
                               redirect_uri=callback,
                               scope=SCOPE,
                               user_agent=USER_AGENT)

    # Exchange the code (in self.request.params) for an access token.
    credentials = flow.step2_exchange(self.request.params)
    http = credentials.authorize(httplib2.Http())

    bucket = self.request.get('state')
    storage = build_service('storage', 'v1beta1', http=http)
    list_resp = storage.objects().list(bucket=bucket, fields=FIELDS).execute()

    self.response.headers['Content-Type'] = 'text/xml'
    self.response.out.write(JsonListingToXml(bucket, list_resp))


def main():
  application = webapp.WSGIApplication(
      [
          ('/oauth2callback', AuthHandler),
          ('/..*', MainHandler)
      ],
      debug=True)
  run_wsgi_app(application)


if __name__ == '__main__':
  main()
