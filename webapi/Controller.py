import os
import threading
import Util

__author__ = 'rohan'


from bottle import route, get, post,error
import bottle
import json

bottle.debug()
os.chdir(os.path.dirname(__file__))

bottle.TEMPLATE_PATH.insert(0,'./static')
app = bottle.app()

@post("/:ts/:stz/postback/")
@bottle.view("testing")
def handler(ts,stz):

    hash = bottle.request.POST['hash']
    data = bottle.request.POST['payload']
    print "HASH ==> "+hash
    print "PAYLOAD ==> "+data

    if Util.checkHash(hash,data):
        account = bottle.request.urlparts[1].split(".")[0]
        ip  = str(bottle.request['REMOTE_ADDR'])
        Util.saveData(account,ip,ts,stz,data)

        print "saved data for account %s " % account
        return "success"
    return "error"

@get('/main')

def handler():
    print "reached here"
    return "hi"
@error(404)
def handler():
    print "reached here"

    return "wrong url ,please try again"