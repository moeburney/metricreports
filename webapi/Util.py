from hashlib import md5
import json
import threading
from pymongo.errors import OperationFailure

__author__ = 'rohan'

import pymongo
connection = pymongo.Connection('localhost', 27017)
def checkHash(hash,data):
    currenthash = md5(data).hexdigest()
    if currenthash == hash:
        print "currhash ==> %s == %s" %(currenthash,hash)
        return True
    return False

def processNext(account,ip,ts,stz,rawdata):
    data = json.loads(rawdata)
    data['ts'] = int(ts)
    data['stz'] = str(stz)
    ip = ip.replace(".","")
    db = connection["acc-"+account]
    #accountmeta = db["meta"]
    # find if key from rawdata matches key stored in our database
    # procceed if it matches
    datacoll = db["data_"+ip]
    #metacoll , update brief details about server and etc
    try:

        print "Operation : Insert  id [%s]" % datacoll.insert(data,safe=True)

    except OperationFailure,e:
        print str(e)
def saveData(account,ip,ts,stz,rawdata):
    print "starting save thread"
    threading.Thread(target=processNext,args=(account,ip,ts,stz,rawdata)).start()