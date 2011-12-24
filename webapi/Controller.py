import json
import os
import threading
from beaker.middleware import SessionMiddleware
from pymongo import json_util
import Util
import keys

__author__ = 'rohan'


from bottle import route, get, post,error
import bottle

bottle.debug()
os.chdir(os.path.dirname(__file__))

bottle.TEMPLATE_PATH.insert(0,'./static')



session_opts = {
    'session.auto': True,
    'session.timeout': 3000,
    'session.type': 'ext:database',
    'session.url': 'mysql://rohan:gotohome@localhost/ron',
    'session.key': 'campaignsession',
    'session.secret': 'gotohome',
    'session.lock_dir': './'
}
app = SessionMiddleware(bottle.app(), session_opts)

def get_session():
    return bottle.request.environ.get('beaker.session')


def validate_login():
    session = get_session()
    if 'uid' in session and 'loggedin' in session:
        if session['loggedin']:
            return True
    else:
        return False


def auth(check_func=validate_login):
    def decorator(view):
        def wrapper(*args, **kwargs):
            auth = check_func()
            if auth:
                return view(*args, **kwargs)
            return bottle.HTTPError(code=401,output="Access Denied")


        return wrapper

    return decorator


def logout():
    sess = get_session()
    sess.delete()


def login(account,user, passwd):
    user = Util.auth(account,user,passwd)
    if user:
        sess = get_session()
        sess['uid'] = user[keys.USER_UID]
        sess['loggedin'] = True
    else:
        return
@post('/login')
def handler():
    login(Util.getSubDomain(bottle.request),bottle.request.POST.get('email'), bottle.request.POST.get('passwd'))
    if not validate_login():
        return {keys.RESULT_STR:keys.RESULT_ERROR,keys.REASON_STR:keys.REASON_INVALID_LOGIN}
    return {keys.RESULT_STR:keys.RESULT_SUCCESS}

@get('/logout')
def handler():
    logout()
    bottle.redirect('/index.html')
@post("/:ts/:stz/postback/")
@bottle.view("testing")
def handler(ts,stz):

    hash = bottle.request.POST['hash']
    data = bottle.request.POST['payload']
    print "HASH ==> "+hash
    print "PAYLOAD ==> "+data

    if Util.checkHash(hash,data):
        account = Util.getSubDomain(bottle.request)
        ip  = str(bottle.request['REMOTE_ADDR'])
        Util.saveData(account,ip,ts,stz,data)

        print "saved data for account %s " % account
        return "success"
    return "error"

@post('/users')
def handler():
    return Util.createUser(Util.getSubDomain(bottle.request),bottle.request.POST['email'],bottle.request.POST['passwd'])

@get('/servers')
@auth()
def handler():
    return json.dumps(Util.getServers(Util.getSubDomain(bottle.request)),default=json_util.default)

@get('/servers/:ip')
@auth()
def handler(ip):
    return json.dumps(Util.getLatestSnapShot(Util.getSubDomain(bottle.request),ip),default=json_util.default)

@get('/servers/:ip/alerts')
@bottle.view('new_alert')
@auth()
def handler(ip):
    return dict()
@get('/servers/:ip/meta')
@auth()
def handler(ip):
    return json.dumps(Util.getServerMeta(Util.getSubDomain(bottle.request),ip),default=json_util.default)
@get('/test')
@auth()
def handler():
    print "reached here"
    return "hi"
