#!/usr/bin/env python
#
# Copyright 2007 Google Inc.
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


from google.appengine.ext import webapp
from google.appengine.ext.webapp import util
from google.appengine.ext import db
from django.utils import simplejson as json
import hashlib
from datetime import datetime
from exceptions import ValueError
import re
import logging

class Redditor(db.Model):
  userID = db.StringProperty()
  password = db.StringProperty()
  @classmethod
  def hashPass(cls, password):
    m = hashlib.new('md5')
    m.update(password)
    return m.hexdigest()
    
  @classmethod
  def get(cls, userID, password):
    redditor = Redditor.get_by_key_name(userID)
    if((redditor == None) or (redditor.password != Redditor.hashPass(password))):
      return None
    return redditor
    
class Bookmark(db.Model):
  creator = db.ReferenceProperty(Redditor)
  page = db.StringProperty()
  comment = db.StringProperty() 
  link = db.LinkProperty()
  addedOn = db.DateTimeProperty()

class RetrieveBookmarks(webapp.RequestHandler):
  def get(self):
    if not self.request.get('u'):
      self.response.headers.add_header('Content-type', 'text/html')
      self.response.out.write('<html><body>')
      self.response.out.write("<h2>Reddit Comment Bookmarks - Pranav K</h2>")
      self.response.out.write('<a href="/printsource">View Source</a>')
      self.response.out.write('</body></html>')
      
      return
    self.__handleRequest()
      
  def post(self):
      self.__handleRequest()
      
  def __handleRequest(self):
    out = self.response.out
    if self.request.get('jsonp'):
      out.write('%s(' % self.request.get('jsonp'))
    if self.request.get('u') and self.request.get('p'):
      self.response.headers['Content-type'] = 'application/json'
      creator = Redditor.get(self.request.get('u'), self.request.get('p'))
      if not creator:
        out.write('[]')
        return
      try:
          offset = int(self.request.get('o'))
          offset = 0 if offset < 0 else offset
      except ValueError:
        offset = 0
      bookmarks = Bookmark.all()
      bookmarks.filter("creator = ",  creator.key())
      bookmarks.order("-addedOn")
      if self.request.get('pg'):
        bookmarks.filter("page", self.request.get('pg'))
        results = bookmarks.fetch(10) #Limit the number of bookmarks we'll bother to tag as unsave-able to 10
      else:
        results = bookmarks.fetch(10, offset)
      if len(results) > 0:
        links = [x.link for x in results]
        out.write(json.dumps(links))
      else:
        out.write('[]')
      if(self.request.get('jsonp')):
        out.write(');')
    else:
      self.response.set_status(400)

class AddBookmark(webapp.RequestHandler):
  def get(self):
    self.__handleRequest()

  def post(self):
    self.__handleRequest()

  def __handleRequest(self):
    if not self.request.get('u') or not self.request.get('p'):
      self.response.set_status(400)
      return
      
    link = self.request.get('l').strip()
    commentLinkRegex = re.compile("/r/[^/]+/comments/([a-z0-9]+)/(?:[^/]+/)?([a-z0-9]+)$")
    commentInfo = commentLinkRegex.search(link)
    if not commentInfo:
      self.response.set_status(400)
      logging.error('Malformed link: %s' % link)
      return
    else:
      commentInfo = commentInfo.groups()
    
    creator = Redditor.get(self.request.get('u'), self.request.get('p'))
    if not creator:
      creator = Redditor(userID=self.request.get('u'), password=Redditor.hashPass(self.request.get('p')))
      creator.put()
    
    Bookmark(creator=creator,
      link=db.Link(self.request.get('l')), 
      addedOn=datetime.now(),
      page=commentInfo[0],
      comment=commentInfo[1]
    ).put()
    if(self.request.get('jsonp')):
      self.response.out.write('%s("OK")' % self.request.get('jsonp'))
    else:
      self.response.out.write('OK')

class RemoveBookmark(webapp.RequestHandler):
  def get(self):
    self.__handleRequest()
    
  def post(self):
    self.__handleRequest()
    
  def __handleRequest(self):
    creator = Redditor.get(self.request.get('u'), self.request.get('p'))
    if not creator:
      self.response.set_status(500)
      return
    b = Bookmark.gql('Where creator = :1 and link = :2', creator.key(), self.request.get('l')).get()
    if b:
      b.delete()
    if(self.request.get('jsonp')):
      self.response.out.write('%s("OK")' % self.request.get('jsonp'))
    else:
      self.response.out.write('OK')

class PrintSelf(webapp.RequestHandler):
  def get(self):
    import os, cgi
    out = self.response.out
    self.response.headers.add_header("content-type", "text/html")
    out.write('<html><head><title>Reddit Comment Bookmarks - Source</title></head>')
    out.write('<body><pre>')
    for line in file(os.environ['PATH_TRANSLATED']):
      out.write(cgi.escape(line))
    out.write('</pre></body>')
    out.write('</html>')

def main():
  application = webapp.WSGIApplication([('/', RetrieveBookmarks),
                                                        ('/save', AddBookmark),
                                                        ('/unsave', RemoveBookmark),
                                                        ('/printsource', PrintSelf)
                                                        ],
                                       debug=True )
  util.run_wsgi_app(application)


if __name__ == '__main__':
  main()
