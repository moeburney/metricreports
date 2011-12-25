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

@get('/users')
@auth()
def handler():
    raw_users =  Util.getUsers(Util.getSubDomain(bottle.request))
    users = []

    for user in raw_users:
        users.append(user)
    return json.dumps(users,default=json_util.default)
@get('/servers')
@auth()
def handler():
    return json.dumps(Util.getServers(Util.getSubDomain(bottle.request)),default=json_util.default)

@get('/servers/:ip')
@auth()
def handler(ip):
    return json.dumps(Util.getLatestSnapShot(Util.getSubDomain(bottle.request),ip),default=json_util.default)


@get('/servers/:ip/disks')
@auth()
def handler(ip):
    return json.dumps(Util.getLatestDiskOverView(Util.getSubDomain(bottle.request),ip),default=json_util.default)

@get('/servers/:ip/processes')
@auth()
def handler(ip):
    return json.dumps(Util.getLatestProcessOverView(Util.getSubDomain(bottle.request),ip),default=json_util.default)

@get('/servers/:ip/alerts')
@bottle.view('new_alert')
@auth()
def handler(ip):
    if bottle.request.get_header("Accept") == "application/json":
        return json.dumps(Util.getAlertsForIp(Util.getSubDomain(bottle.request),ip),default=json_util.default)
    return dict()

@get('/servers/:ip/alerts.json')
@bottle.view('new_alert')
@auth()
def handler(ip):
    raw_alerts = Util.getAlertsForIp(Util.getSubDomain(bottle.request),ip)
    alerts = []
    for alert in raw_alerts:
        alerts.append(alert)
    return json.dumps(alerts,default=json_util.default)



@get('/servers/:ip/diskalert')
@bottle.view('new_diskalert')
@auth()
def handler(ip):
    if bottle.request.get_header("Accept") == "application/json":
        return json.dumps(Util.getAlertsForIp(Util.getSubDomain(bottle.request),ip),default=json_util.default)
    return dict()
@get('/servers/:ip/processalert')
@bottle.view('new_processalert')
@auth()
def handler(ip):
    if bottle.request.get_header("Accept") == "application/json":
        return json.dumps(Util.getAlertsForIp(Util.getSubDomain(bottle.request),ip),default=json_util.default)
    return dict()

@get('/servers/:ip/ramalert')
@bottle.view('new_ramalert')
@auth()
def handler(ip):
    if bottle.request.get_header("Accept") == "application/json":
        return json.dumps(Util.getAlertsForIp(Util.getSubDomain(bottle.request),ip),default=json_util.default)
    return dict()

@get('/servers/:ip/loadavgalert')
@bottle.view('new_loadavgalert')
@auth()
def handler(ip):
    if bottle.request.get_header("Accept") == "application/json":
        return json.dumps(Util.getAlertsForIp(Util.getSubDomain(bottle.request),ip),default=json_util.default)
    return dict()



@post('/servers/:ip/diskalert')
@auth()
def handler(ip):
    return json.dumps(Util.createDiskAlert(Util.getSubDomain(bottle.request),ip,bottle.request.POST),default=json_util.default)

@post('/servers/:ip/processalert')
@auth()
def handler(ip):
    return json.dumps(Util.createProcessAlert(Util.getSubDomain(bottle.request),ip,bottle.request.POST),default=json_util.default)

@post('/servers/:ip/ramalert')
@auth()
def handler(ip):
    return json.dumps(Util.createRamAlert(Util.getSubDomain(bottle.request),ip,bottle.request.POST),default=json_util.default)

@post('/servers/:ip/loadavgalert')
@auth()
def handler(ip):
    return json.dumps(Util.createLoadAvgAlert(Util.getSubDomain(bottle.request),ip,bottle.request.POST),default=json_util.default)


@get('/servers/:ip/meta')
@auth()
def handler(ip):
    return json.dumps(Util.getServerMeta(Util.getSubDomain(bottle.request),ip),default=json_util.default)



@get('/test')
@auth()
def handler():
    print "reached here"
    return "hi"
