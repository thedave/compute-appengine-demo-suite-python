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

"""Main page for the Google Compute Engine demo suite."""

from __future__ import with_statement

__author__ = 'kbrisbin@google.com (Kathryn Hurley)'

import json

import lib_path
import google_cloud.gce as gce
import google_cloud.gce_exception as error
import google_cloud.oauth as oauth
import jinja2
import oauth2client.appengine as oauth2client
import user_data
import webapp2

from google.appengine.api import users

DEMO_NAME = 'quick-start'
REVOKE_URL = 'https://accounts.google.com/o/oauth2/revoke'
MAX_RESULTS = 100

jinja_environment = jinja2.Environment(loader=jinja2.FileSystemLoader(''))
oauth_decorator = oauth.decorator
parameters = [
    user_data.DEFAULTS[user_data.GCE_PROJECT_ID]
]
data_handler = user_data.DataHandler(DEMO_NAME, parameters)


class QuickStart(webapp2.RequestHandler):
  """Show main Quick Start demo page."""

  @oauth_decorator.oauth_required
  @data_handler.data_required
  def get(self):
    """Displays the main page for the Quick Start demo. Auth required."""

    if not oauth_decorator.credentials.refresh_token:
      self.redirect(oauth_decorator.authorize_url() + '&approval_prompt=force')
    variables = {'demo_name': DEMO_NAME}
    template = jinja_environment.get_template(
        'demos/%s/templates/index.html' % DEMO_NAME)
    self.response.out.write(template.render(variables))


class Instance(webapp2.RequestHandler):
  """List or start instances."""

  @oauth_decorator.oauth_required
  @data_handler.data_required
  def get(self):
    """List instances using the gce_appengine helper class.

    Return the results as JSON mapping instance name to status.
    """

    gce_project_id = data_handler.stored_user_data[user_data.GCE_PROJECT_ID]
    gce_project = gce.GceProject(
        oauth_decorator.credentials, project_id=gce_project_id)

    try:
      instances = gce_project.list_instances(
            filter='name eq ^%s.*' % DEMO_NAME, maxResults=MAX_RESULTS)
    except error.GceError, e:
      self.response.set_status(500, 'Error getting instances: ' + e.message)
      self.response.headers['Content-Type'] = 'application/json'
      return
    except error.GceTokenError:
      self.response.set_status(401, 'Unauthorized.')
      self.response.headers['Content-Type'] = 'application/json'
      return

    instance_dict = {}
    for instance in instances:
      instance_dict[instance.name] = {'status': instance.status}
    json_instances = json.dumps(instance_dict)
    self.response.headers['Content-Type'] = 'application/json'
    self.response.out.write(json_instances)

  @data_handler.data_required
  def post(self):
    """Start instances using the gce_appengine helper class."""

    gce_project_id = data_handler.stored_user_data[user_data.GCE_PROJECT_ID]
    user_id = users.get_current_user().user_id()
    credentials = oauth2client.StorageByKeyName(
        oauth2client.CredentialsModel, user_id, 'credentials').get()
    gce_project = gce.GceProject(credentials, project_id=gce_project_id)

    num_instances = int(self.request.get('num_instances'))
    instances = [gce.Instance('%s-%d' % (DEMO_NAME, i))
                 for i in range(num_instances)]

    try:
      gce_project.bulk_insert(instances)
    except error.GceError, e:
      self.response.set_status(500, 'Error inserting instances: ' + e)
      self.response.headers['Content-Type'] = 'application/json'
      return
    except error.GceTokenError:
      self.response.set_status(401, 'Unauthorized.')
      self.response.headers['Content-Type'] = 'application/json'
      return

    self.response.headers['Content-Type'] = 'text/plain'
    self.response.out.write('starting cluster')


class Cleanup(webapp2.RequestHandler):
  """Stop instances."""

  @data_handler.data_required
  def post(self):
    """Stop instances using the gce_appengine helper class."""
    gce_project_id = data_handler.stored_user_data[user_data.GCE_PROJECT_ID]
    user_id = users.get_current_user().user_id()
    credentials = oauth2client.StorageByKeyName(
        oauth2client.CredentialsModel, user_id, 'credentials').get()
    gce_project = gce.GceProject(credentials, project_id=gce_project_id)

    try:
      instances = gce_project.list_instances(
            filter='name eq ^%s.*' % DEMO_NAME, maxResults=MAX_RESULTS)
      gce_project.bulk_delete(instances)
    except error.GceError, e:
      self.response.set_status(500, 'Error deleting instances: ' + e.message)
      self.response.headers['Content-Type'] = 'application/json'
      return
    except error.GceTokenError:
      self.response.set_status(401, 'Unauthorized.')
      self.response.headers['Content-Type'] = 'application/json'
      return

    self.response.headers['Content-Type'] = 'text/plain'
    self.response.out.write('stopping cluster')


app = webapp2.WSGIApplication(
    [
        ('/%s' % DEMO_NAME, QuickStart),
        ('/%s/instance' % DEMO_NAME, Instance),
        ('/%s/cleanup' % DEMO_NAME, Cleanup),
        (data_handler.url_path, data_handler.data_handler),
    ],
    debug=True)
