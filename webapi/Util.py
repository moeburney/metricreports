from hashlib import md5
import json
import sched
import threading
from pymongo.errors import OperationFailure
import time
import keys

__author__ = 'rohan'

import pymongo
from sendmail import Sendmail
connection = pymongo.Connection('localhost', 27017)
sender = Sendmail()
sender.set_debuglevel(True)
AlertsCheckInterval  = 30
def startalertthread():
    s = sched.scheduler(time.time, time.sleep)
    doAlertChecks()
    s.run()
    return
def doAlertChecks():
    accounts = getAccounts()
    for account in accounts:
        openalerts = getOpenAlerts(account)
        for item in openalerts:
            handleAlert(item)
    sc.enter(AlertsCheckInterval, 1, doAlertChecks)
threading.Thread(target=startalertthread).start()

def handleAlert(openalert):
    if openalert[keys.OPEN_ALERT_STATUS] == keys.OPEN_ALERT_STATUS_ON:
        count = openalert[keys.OPEN_ALERT_COUNT]
        if count>0:
            accountinfo = getaccountinfostr(openalert[keys.ACC_PREFIX],openalert[keys.SERVER_PUBLIC_IP])
            while count>0:
                sendemail(openalert[keys.OPEN_ALERT_TONOTIFY],openalert[keys.ALERT_TYPE_STR],openalert[keys.OPEN_ALERT_DATA],accountinfo)
                count -= 1
        db = getdb(openalert[keys.ACC_PREFIX])
        openAlertsColl = db[keys.OPEN_ALERTS_PREFIX+openalert[keys.SERVER_PUBLIC_IP].replace(".","")]
        openAlertsColl.update({keys.OPEN_ALERT_AID:openalert[keys.OPEN_ALERT_AID]},{"$set":{keys.OPEN_ALERT_COUNT:count}},safe=True)
def sendemail(emaillist,subject,body,otherinfo):
    finalbody = "Subject: %s \n\n %s \n %s" %(subject,otherinfo,body)
    sender.sendmail("mail@testing.com",emaillist,finalbody)
def getOpenAlerts(account):
    db = getdb(account,prefix=False)
    collNames = db.collection_names()
    openAlerts = []
    for name in collNames:
        if keys.OPEN_ALERTS_PREFIX in name:
            coll = db[name]
            openAlerts.extend(getAll(coll))
    return openAlerts
def getAllOpenAlerts(coll):
    items = []
    for item in coll.find({keys.OPEN_ALERT_STATUS:keys.OPEN_ALERT_STATUS_ON}):
        items.append(item)
    return items
def getAccounts():
    accounts = []
    for dbname in connection.database_names():
        if keys.ACC_PREFIX in dbname:
            accounts.append(dbname)
    return accounts
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
        metacoll.update({},metadata,safe=True)
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
    if alerts == 0 or alerts is None:
        return
    for alert in alerts:
        tonotify = alert[keys.ALERT_SEND_EMAIL] # currently just email.
        if alert[keys.ALERT_TYPE_STR] == keys.ALERT_DISK:
            isDiskAlert,data = checkDiskAlert(alert)
            if isDiskAlert:
                createOpenAlert(keys.ALERT_DISK,alert[keys.OID],tonotify,data,account,ip)
            if not isDiskAlert:
                removeOldAlert(account,ip,alert[keys.OID])
        if alert[keys.ALERT_TYPE_STR] == keys.ALERT_PROCESS:
            isProcessAlert,data = checkProcessAlert(alert)
            if isProcessAlert:
                # save the alert
                createOpenAlert(keys.ALERT_PROCESS,alert[keys.OID],tonotify,data,account,ip)
            if not isProcessAlert:
                removeOldAlert(account,ip,alert[keys.OID])
        if alert[keys.ALERT_TYPE_STR] == keys.ALERT_RAM:
            isRamAlert,data = checkRamAlert(alert)
            if isRamAlert:
                createOpenAlert(keys.ALERT_RAM,alert[keys.OID],tonotify,data,account,ip)
            if not isRamAlert:
                removeOldAlert(account,ip,alert[keys.OID])
        if alert[keys.ALERT_LOADAVG] == keys.ALERT_LOADAVG:
            isLoadAvgAlert,data = checkLoadAvgAlert(alert)
            if isLoadAvgAlert:
                createOpenAlert(keys.ALERT_LOADAVG,alert[keys.OID],tonotify,data,account,ip)
            if not isLoadAvgAlert:
                removeOldAlert(account,ip,alert[keys.OID])


def removeOldAlert(account,ip,aid):
    db = getdb(account)
    openAlertsColl = db[keys.OPEN_ALERTS_PREFIX+ip.replace(".","")]
    openAlertsColl.update({keys.OPEN_ALERT_AID:aid},{"$set":{keys.OPEN_ALERT_STATUS:keys.OPEN_ALERT_STATUS_OFF}},safe=True)




def createOpenAlert(ty,alertid,notifylist,data,account,ip):
    db = getdb(account)
    openalertColl = db[keys.OPEN_ALERTS_PREFIX+ip.replace(".","")]
    openalert = dict()
    openalert[keys.TIMESTAMP] = time.time()
    openalert[keys.ACC_PREFIX] = account
    openalert[keys.SERVER_PUBLIC_IP] = ip
    openalert[keys.ALERT_TYPE_STR] = ty
    openalert[keys.OPEN_ALERT_TONOTIFY] = notifylist
    openalert[keys.OPEN_ALERT_DATA] = data
    openalert[keys.OPEN_ALERT_AID] = alertid
    openalert[keys.OPEN_ALERT_FOR] = 0
    openalert[keys.OPEN_ALERT_EVERY] = 0
    openalert[keys.OPEN_ALERT_STATUS] = keys.OPEN_ALERT_STATUS_ON
    openalert = openalertColl.find_and_modify(query={keys.OPEN_ALERT_AID:alertid},update=openalertColl,upsert=True,new=True)
    openalertColl.update({keys.OID:openalert[keys.OID]},{"$inc":{keys.OPEN_ALERT_COUNT:1}},safe=True)

def getLatestSnapShot(account,ip):
    return getLastXSnapShot(account,ip,1)




def checkDiskAlert(alert):
    hddName = alert[keys.ALERT_MAIN_OPERAND]
    ip = alert[keys.ALERT_FOR_IP]
    account = alert[keys.ALERT_FOR_ACCOUNT]
    option = alert[keys.ALERT_MAJOR_OPTION]
    operator = alert[keys.ALERT_OPERATOR]
    rightoperand = alert[keys.ALERT_SEC_OPERAND]
    latestSnapShot = getLatestSnapShot(account,ip)
    for hdd in latestSnapShot[keys.SERVER_DISK_USAGE]:
        if hddName == hdd[0]:
            if option == keys.USED:
                if operator == keys.OPERATOR_GREATER:
                    if hdd[2] > rightoperand:
                        return True,"Alert, Disk Space used for partition %s is greater than %s" %(hddName,rightoperand)
                if operator == keys.OPERATOR_EQUAL:
                    if hdd[2] == rightoperand:
                        return True,"Alert, Disk Space used for partition %s is equal to %s" %(hddName,rightoperand)
                if operator == keys.OPERATOR_LESS:
                    if hdd[2] < rightoperand:
                        return True,"Alert, Disk Space used for partition %s is less than %s" %(hddName,rightoperand)
            if option == keys.FREE:
                if operator == keys.OPERATOR_GREATER:
                    if hdd[3] > rightoperand:
                        return True,"Alert, Disk Space free for partition %s is greater than %s" %(hddName,rightoperand)
                if operator == keys.OPERATOR_EQUAL:
                    if hdd[3] == rightoperand:
                        return True,"Alert, Disk Space free for partition %s is equal to %s" %(hddName,rightoperand)
                if operator == keys.OPERATOR_LESS:
                    if hdd[3] < rightoperand:
                        return True,"Alert, Disk Space free for partition %s is less than %s" %(hddName,rightoperand)
            if option == keys.PERCENTAGE_USED:
                phdd = int(hdd[4].replace("%",""))
                if operator == keys.OPERATOR_GREATER:

                    if phdd > rightoperand:
                        return True,"Alert, Disk Space used(%%) for partition %s is greater than %s" %(hddName,rightoperand)
                if operator == keys.OPERATOR_EQUAL:
                    if phdd == rightoperand:
                        return True,"Alert, Disk Space used(%%) for partition %s is equal to %s" %(hddName,rightoperand)
                if operator == keys.OPERATOR_LESS:
                    if phdd < rightoperand:
                        return True,"Alert, Disk Space used(%%) for partition %s is less than %s" %(hddName,rightoperand)
    return False,""



def checkProcessAlert(alert):
    ProcessName = alert[keys.ALERT_MAIN_OPERAND]
    ip = alert[keys.ALERT_FOR_IP]
    account = alert[keys.ALERT_FOR_ACCOUNT]
   # option = alert[keys.ALERT_MAJOR_OPTION]
    operator = alert[keys.ALERT_OPERATOR]
    #rightoperand = alert[keys.ALERT_SEC_OPERAND]
    latestSnapShot = getLatestSnapShot(account,ip)
    plist = []
    for process in latestSnapShot[keys.PROCESSES]:
        plist.append(process[10])
    if operator == keys.OPERATOR_EXISTS:
        if ProcessName not in plist:
            return True,"Alert, Process '%s' does not exist" %ProcessName
    if operator == keys.OPERATOR_PARTIAL_MATCH:
        atleastone = False
        for pname in plist:
            if ProcessName in pname:
                atleastone = True
        if not atleastone:
            return True,"Alert Process which contain %s does not exist" %ProcessName

    return False,""



def checkRamAlert(alert):
    ip = alert[keys.ALERT_FOR_IP]
    account = alert[keys.ALERT_FOR_ACCOUNT]
    option = alert[keys.ALERT_MAJOR_OPTION]
    operator = alert[keys.ALERT_OPERATOR]
    rightoperand = alert[keys.ALERT_SEC_OPERAND]
    latestSnapShot = getLatestSnapShot(account,ip)
    used = latestSnapShot[keys.MEM_USED]
    free = latestSnapShot[keys.MEM_FREE]
    if option == keys.USED:
        if operator == keys.OPERATOR_GREATER:
            if used > rightoperand:
                return True,"Alert, Physical Memory used is greater than %s" %rightoperand
        if operator == keys.OPERATOR_EQUAL:
            if used == rightoperand:
                return True,"Alert, Physical Memory used is equal to %s" %rightoperand
        if operator == keys.OPERATOR_LESS:
            if used < rightoperand:
                return True,"Alert, Physical Memory used is less than %s" %rightoperand
    if option == keys.FREE:
        if operator == keys.OPERATOR_GREATER:
            if free > rightoperand:
                return True,"Alert, Physical Memory free is greater than %s" %rightoperand
        if operator == keys.OPERATOR_EQUAL:
            if free == rightoperand:
                return True,"Alert, Physical Memory free is equal to %s" %rightoperand
        if operator == keys.OPERATOR_LESS:
            if free < rightoperand:
                return True,"Alert, Physical Memory free is less than %s" %rightoperand
    return False,""



def checkLoadAvgAlert(alert):
    ip = alert[keys.ALERT_FOR_IP]
    account = alert[keys.ALERT_FOR_ACCOUNT]
    operator = alert[keys.ALERT_OPERATOR]
    option = alert[keys.ALERT_MAJOR_OPTION] # enter minutes till load avg is the rightoperand
    rightoperand = alert[keys.ALERT_SEC_OPERAND]
    lastfewSnapShots = getLastXSnapShots(account,ip,option)
    loadlist = []
    for snapshot in lastfewSnapShots:
        loadlist.append(float(snapshot[keys.LOADAVG]))
    loadavg = mean(loadlist)
    if operator == keys.OPERATOR_GREATER:
        if loadavg > rightoperand:
            return True,"Alert, LoadAverage is greater than %s" %rightoperand
    if operator == keys.OPERATOR_EQUAL:
        if loadavg == rightoperand:
            return True,"Alert, LoadAverage is equal to %s" %rightoperand
    if operator == keys.OPERATOR_LESS:
        if loadavg < rightoperand:
            return True,"Alert, LoadAverage is less than %s" %rightoperand
    return False,""


def getAlertsForIp(account,ip):
    db = getdb(account)
    alertscoll = db[keys.SAVED_ALERTS_PREFIX+ip.replace(".","")]
    alerts = alertscoll.find({keys.ACC_ALERTS_APPLYTO:ip})
    if alerts is None:
        return 0
    if alerts.count() <=0:
        return 0
    return alerts


def mean(numberList):
    if len(numberList) == 0:
        return float('nan')
    floatNums = [float(x) for x in numberList]
    return sum(floatNums) / len(numberList)



def getLastXSnapShot(account,ip,count):
    db = getdb(account)
    dataColl = db[keys.DATA_PREFIX+ip.replace(".","")]
    return dataColl.find().sort({keys.TIMESTAMP:pymongo.DESCENDING}).limit(count)


def getdb(account,prefix=True):
    if not prefix:
        return connection[account]
    return connection[keys.ACC_PREFIX+account]
