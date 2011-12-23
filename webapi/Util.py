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
def checkRamAlert(alert,ip):
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
    option = alert[keys.ALERT_MAJOR_OPTION]
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
def getAlertsForIp(account):
    db = getdb(account)
    alertscoll = db[keys.ACC_SAVED_ALERTS+ip.replace(".","")]
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


def getdb(account):
    return connection[keys.ACC_PREFIX+account]