'''
	metrics bot
	www.metrics-bot.com
	----
	Server monitoring bot for Linux, FreeBSD and Mac OS X

	Licensed under Simplified BSD License (see LICENSE)
'''

#
# Why are you using this?
#
import time

print 'Note: This script is for automating deployments and is not the normal way to install the SD bot. See http://www.metrics-bot.com/docs/bot/installation/'
print 'Continuing in 4 seconds...'
time.sleep(4)

#
# Argument checks
#
import sys

if len(sys.argv) < 5:
    print 'Usage: python mt-deploy.py [API URL] [SD URL] [username] [password] [[init]]'
    sys.exit(2)

#
# Get server details
#

import socket

# IP
try:
    serverIp = socket.gethostbyname(socket.gethostname())

except socket.error, e:
    print 'Unable to get server IP: ' + str(e)
    sys.exit(2)

# Hostname
try:
    serverHostname = hostname = socket.getfqdn()

except socket.error, e:
    print 'Unable to get server hostname: ' + str(e)
    sys.exit(2)

#
# Get latest bot version
#

print '1/4: Downloading latest bot version';

import httplib
import urllib2

# Request details
try:
    requestbot = urllib2.urlopen('http://www.metrics-bot.com/botupdate/')
    responsebot = requestbot.read()

except urllib2.HTTPError, e:
    print 'Unable to get latest version info - HTTPError = ' + str(e)
    sys.exit(2)

except urllib2.URLError, e:
    print 'Unable to get latest version info - URLError = ' + str(e)
    sys.exit(2)

except httplib.HTTPException, e:
    print 'Unable to get latest version info - HTTPException'
    sys.exit(2)

except Exception, e:
    import traceback

    print 'Unable to get latest version info - Exception = ' + traceback.format_exc()
    sys.exit(2)

#
# Define downloader function
#

import md5 # I know this is depreciated, but we still support Python 2.4 and hashlib is only in 2.5. Case 26918
import urllib

def downloadFile(botFile, recursed=False):
    print 'Downloading ' + botFile['name']

    downloadedFile = urllib.urlretrieve('http://www.metrics-bot.com/downloads/mt-bot/' + botFile['name'])

    # Do md5 check to make sure the file downloaded properly
    checksum = md5.new()
    f = file(downloadedFile[0], 'rb')

    # Although the files are small, we can't guarantee the available memory nor that there
    # won't be large files in the future, so read the file in small parts (1kb at time)
    while True:
        part = f.read(1024)

        if not part:
            break # end of file

        checksum.update(part)

    f.close()

    # Do we have a match?
    if checksum.hexdigest() == botFile['md5']:
        return downloadedFile[0]

    else:
        # Try once more
        if recursed == False:
            downloadFile(botFile, True)

        else:
            print botFile[
                  'name'] + ' did not match its checksum - it is corrupted. This may be caused by network issues so please try again in a moment.'
            sys.exit(2)

#
# Install the bot files
#

# We need to return the data using JSON. As of Python 2.6+, there is a core JSON
# module. We have a 2.4/2.5 compatible lib included with the bot but if we're
# on 2.6 or above, we should use the core module which will be faster
import platform

pythonVersion = platform.python_version_tuple()

# Decode the JSON
if int(pythonVersion[1]) >= 6: # Don't bother checking major version since we only support v2 anyway
    import json

    try:
        updateInfo = json.loads(responsebot)
    except Exception, e:
        print 'Unable to get latest version info. Try again later.'
        sys.exit(2)

else:
    try:
        updateInfo = minjson.safeRead(responsebot)
    except Exception, e:
        print 'Unable to get latest version info. Try again later.'
        sys.exit(2)

# Loop through the new files and call the download function
for botFile in updateInfo['files']:
    botFile['tempFile'] = downloadFile(botFile)

# If we got to here then everything worked out fine. However, all the files are still in temporary locations so we need to move them
import os
import shutil # Prevents [Errno 18] Invalid cross-device link (case 26878) - http://mail.python.org/pipermail/python-list/2005-February/308026.html

# Make sure doesn't exist already
if os.path.exists('mt-bot/'):
    shutil.rmtree('mt-bot/')

os.mkdir('mt-bot')

for botFile in updateInfo['files']:
    print 'Installing ' + botFile['name']

    if botFile['name'] != 'config.cfg':
        shutil.move(botFile['tempFile'], 'mt-bot/' + botFile['name'])

print 'bot files downloaded'

#
# Call API to add new server
#

print '2/4: Adding new server'

# Build API payload
import time

timestamp = time.strftime('%a, %d %b %Y %H:%M:%S GMT', time.gmtime())

postData = urllib.urlencode({'name': serverHostname, 'ip': serverIp, 'notes': 'Added by mt-deploy: ' + timestamp})

# Send request
try:
    # Password manager
    mgr = urllib2.HTTPPasswordMgrWithDefaultRealm()
    mgr.add_password(None, sys.argv[1] + '/1.0/', sys.argv[3], sys.argv[4])
    opener = urllib2.build_opener(urllib2.HTTPBasicAuthHandler(mgr), urllib2.HTTPDigestAuthHandler(mgr))

    urllib2.install_opener(opener)

    # Build the request handler
    requestAdd = urllib2.Request(sys.argv[1] + '/1.0/?account=' + sys.argv[2] + '&c=servers/add', postData,
            {'User-Agent': 'metrics bot Deploy'})

    # Do the request, log any errors
    responseAdd = urllib2.urlopen(requestAdd)

    readAdd = responseAdd.read()

except urllib2.HTTPError, e:
    print 'HTTPError = ' + str(e)

    if os.path.exists('mt-bot/'):
        shutil.rmtree('mt-bot/')

except urllib2.URLError, e:
    print 'URLError = ' + str(e)

    if os.path.exists('mt-bot/'):
        shutil.rmtree('mt-bot/')

except httplib.HTTPException, e: # Added for case #26701
    print 'HTTPException' + str(e)

    if os.path.exists('mt-bot/'):
        shutil.rmtree('mt-bot/')

except Exception, e:
    import traceback

    print 'Exception = ' + traceback.format_exc()

    if os.path.exists('mt-bot/'):
        shutil.rmtree('mt-bot/')

# Decode the JSON
if int(pythonVersion[1]) >= 6: # Don't bother checking major version since we only support v2 anyway
    import json

    try:
        serverInfo = json.loads(readAdd)
    except Exception, e:
        print 'Unable to add server.'

        if os.path.exists('mt-bot/'):
            shutil.rmtree('mt-bot/')

        sys.exit(2)

else:
    try:
        serverInfo = minjson.safeRead(readAdd)
    except Exception, e:
        print 'Unable to add server.'

        if os.path.exists('mt-bot/'):
            shutil.rmtree('mt-bot/')

        sys.exit(2)

print 'Server added - ID: ' + str(serverInfo['data']['serverId'])

#
# Write config file
#

print '3/4: Writing config file'

configCfg = '[Main]\nsd_url: http://' + sys.argv[2] + '\nbot_key: ' + serverInfo['data'][
                                                                      'bot_key'] + '\napache_status_url: http://www.example.com/server-status/?auto'

try:
    f = open('mt-bot/config.cfg', 'w')
    f.write(configCfg)
    f.close()

except Exception, e:
    import traceback

    print 'Exception = ' + traceback.format_exc()

    if os.path.exists('mt-bot/'):
        shutil.rmtree('mt-bot/')

print 'Config file written'

#
# Install init.d
#

if len(sys.argv) == 6:
    print '4/4: Installing init.d script'

    shutil.copy('mt-bot/mt-bot.init', '/etc/init.d/mt-bot')

    import subprocess

    print 'Setting permissions'

    df = subprocess.Popen(['chmod', '0755', '/etc/init.d/mt-bot'], stdout=subprocess.PIPE).communicate()[0]

    print 'chkconfig'

    df = subprocess.Popen(['chkconfig', '--add', 'mt-bot'], stdout=subprocess.PIPE).communicate()[0]

    print 'Setting paths'

    path = os.path.realpath(__file__)
    path = os.path.dirname(path)

    df = subprocess.Popen(['ln', '-s', path + '/mt-bot/', '/usr/bin/mt-bot'], stdout=subprocess.PIPE).communicate()[
         0]

    print 'Install completed'

    print 'Launch: /etc/init.d/mt-bot start'

else:
    print '4/4: Not installing init.d script'
    print 'Install completed'

    path = os.path.realpath(__file__)
    path = os.path.dirname(path)

    print 'Launch: python ' + path + '/mt-bot/bot.py start'