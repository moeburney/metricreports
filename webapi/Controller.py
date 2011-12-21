import os

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
    print "HASH ==> "+bottle.request.POST['hash']
    print "PAYLOAD ==> "+bottle.request.POST['payload']
    return dict(request=bottle.request,ts=ts,stz=stz)

@get('/main')

def handler():
    print "reached here"
    return "hi"
@error(404)
def handler():
    print "reached here"

    return "wrong url ,please try again"