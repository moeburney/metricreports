from hashlib import md5
import json
import threading
from pymongo.errors import OperationFailure
import keys

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
    data[keys.TIMESTAMP] = int(ts)
    data[keys.SERVER_TIME_ZONE] = str(stz)
    data[keys.SERVER_PUBLIC_IP] = ip
    __ip = ip
    ip = ip.replace(".","")
    db = getdb(account)
    #accountmeta = db[keys.META_PREFIX+account]
    # find if key from rawdata matches key stored in our database
    # procceed if it matches
    datacoll = db[keys.DATA_PREFIX+ip]
    metacoll= db[keys.META_PREFIX+ip]  #update brief details about server and etc
    metadata = {keys.SERVER_PUBLIC_IP:__ip,keys.SERVER_NICKNAME:data['internalHostname'],keys.ACC_BOT_KEY:data["bot_key"],'lts':int(ts)}

    try:
        metacoll.insert(metadata,safe=True)
        id =datacoll.insert(data,safe=True)
        print "Operation : Insert  id [%s]" % id
        print "Check for Alerts for id [%s]"% id
        checkAlerts(account,__ip)
    except OperationFailure,e:
        print str(e)
def saveData(account,ip,ts,stz,rawdata):
    print "starting save thread"
    threading.Thread(target=processNext,args=(account,ip,ts,stz,rawdata)).start()
def checkAlerts(account,ip):
    alerts = getAlertsForIp(account,ip)
    if alerts == 0:
        return
    for alert in alerts:
        tonotify = alert[keys.ALERT_SEND_EMAIL] # currently just email.
        if alert[keys.ALERT_TYPE_STR] == keys.ALERT_DISK:
            isDiskAlert,data = checkDiskAlert(alert)
            if isDiskAlert:
                sendemail(tonotify,data)
        if alert[keys.ALERT_TYPE_STR] == keys.ALERT_PROCESS:
            isProcessAlert,data = checkProcessAlert(alert)
            if isProcessAlert:
                sendemail(tonotify,data)
        if alert[keys.ALERT_TYPE_STR] == keys.ALERT_RAM:
            isRamAlert,data = checkRamAlert(alert)
            if isRamAlert:
                sendemail(tonotify,data)
        if alert[keys.ALERT_LOADAVG] == keys.ALERT_LOADAVG:
            isLoadAvgAlert,data = checkLoadAvgAlert(alert)
            if isLoadAvgAlert:
                sendemail(tonotify,data)

    # get serverid from alerts array, and check for alert and do action
    #getAlertsFor(account,ip)
    #iterate of alerts, check process alert, disk usage alert, memory alerts. load average alert. [ process alert only check exists, all other check greater than]
    # if alert found, put it in openalerts for the account,
def getLatestSnapShot(account,ip):
    db = getdb(account)
    dataColl = db[keys.DATA_PREFIX+ip.replace(".","")]
    return dataColl.find().sort({keys.TIMESTAMP:pymongo.DESCENDING}).limit(1)
def checkDiskAlert(alert):
    hddName = alert[keys.ALERT_MAIN_OPERAND]
    ip = alert[keys.ALERT_FOR_IP]
    account = alert[keys.ALERT_FOR_ACCOUNT]
    latestSnapShot = getLatestSnapShot(account,ip)
    for hdd in latestSnapShot[keys.SERVER_DISK_USAGE]:
        return
def checkProcessAlert(alert):
    return
def checkRamAlert(alert,ip):
    return
def checkLoadAvgAlert(alert):
    return
def getAlertsForIp(account):
    db = getdb(account)
    alertscoll = db[keys.ACC_SAVED_ALERTS+ip.replace(".","")]
    alerts = alertscoll.find({keys.ACC_ALERTS_APPLYTO:ip})
    if alerts is None:
        return 0
    if alerts.count() <=0:
        return 0
    return alerts




def getdb(account):
    return connection[keys.ACC_PREFIX+account]