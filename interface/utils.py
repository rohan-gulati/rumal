#!/usr/bin/env python
#
# utils.py
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston,
# MA  02111-1307  USA
#
# Author:   Pietro Delsante <pietro.delsante@gmail.com>
#           The Honeynet Project
#

from personalities.Personality import Personality
from pymongo import MongoClient
from bson import ObjectId
from urlparse import urlparse

import base64
import hexdump
import magic
from gridfs import GridFS
from pymongo import MongoClient
from bson import ObjectId

import json

db = MongoClient().thug

def get_personalities():
    return [('', 'Default')] + \
        sorted([(x, y['description'].replace('\t', ' ')) for x, y in Personality().iteritems()], key=lambda x: x[1])

def graph_get_root_node(analysis_id):
    return db.connections.find({"analysis_id": ObjectId(analysis_id)}).sort("chain_id")[0]

def graph_populate_node(analysis_id, url_id):
    if not isinstance(analysis_id, ObjectId):
        analysis_id = ObjectId(analysis_id)
    url         = db.urls.find_one({"_id": url_id})
    location    = db.locations.find_one({"analysis_id": analysis_id, "url_id": url_id}) or {}
    exploits    = [x for x in db.exploits.find({"analysis_id": analysis_id, "url_id": url_id})]

    for key, value in location.iteritems():
        if isinstance(value, ObjectId):
            location[key] = str(value)

    for exploit in exploits:
        for key, value in exploit.iteritems():
            if isinstance(value, ObjectId):
                exploit[key] = str(value)

    node = {
        'url_id'    : str(url_id),
        'url'       : url and url['url'] or '-',
        'domain'    : url and urlparse(url['url']).hostname or '-',
        'location'  : location and location or {},
        'exploits'  : exploits,
        'children'  : []
    }
    return node

def graph_get_children(analysis_id, parent):
    if not isinstance(analysis_id, ObjectId):
        analysis_id = ObjectId(analysis_id)
    if not isinstance(parent['url_id'], ObjectId):
        url_id = ObjectId(parent['url_id'])
    else:
        url_id = parent['url_id']
    for connection in db.connections.find({"analysis_id": analysis_id, "source_id": url_id}):
        node = graph_populate_node(analysis_id, connection['destination_id'])
        node = graph_get_children(analysis_id, node)
        parent['children'].append(node)

    if not parent['children']:
        parent.pop('children')
    return parent

def is_text(mime):
    if mime.startswith('text/'):
        return True

    if mime in ['application/xml']:
        return True

    return False

def make_nested_tree(flat_tree):
    for node in reversed(flat_tree):
        if node['parent'] != None:
            parent_node = flat_tree[node['parent']]
            if 'children' not in parent_node.keys():
                parent_node['children'] = []
            parent_node['children'].append(node)
    return flat_tree[0]


def get_file(object_id):
    # Database MongoClient
    dbfs = MongoClient().thugfs
    fs = GridFS(dbfs)

    #try:
    download_file = base64.b64decode(fs.get(ObjectId(object_id)).read())
    #except:
     #   raise Http404("File not found")

    hexdumped = False
    mime = magic.from_buffer(download_file, mime=True)
    if not is_text(mime):
        download_file = hexdump.hexdump(download_file, result='return')
        hexdumped = True

    # Ensure to use Unicode for the content, else JsonResopnse may fail
    if not isinstance(download_file, unicode):
        download_file = unicode(download_file, errors='ignore')

    return download_file

class Encoder(json.JSONEncoder):
    def default(self, obj, **kwargs):
        if isinstance(obj, ObjectId):
            return str(obj)
        else:
            return json.JSONEncoder.default(obj, **kwargs)


def decoder(dct):
    for k, v in dct.items():
        if '_id' in dct:
            try:
                dct['_id'] = ObjectId(dct['_id'])
            except:
                pass
        return dct

