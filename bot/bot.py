#!/usr/bin/env python
'''
	metrics bot
	www.metrics-bot.com
	----
	Server monitoring bot for Linux, FreeBSD and Mac OS X

	Licensed under Simplified BSD License (see LICENSE)
'''

import logging

# General config
from checks import checks
from daemon import Daemon
import minjson

botConfig = {}
botConfig['logging'] = logging.INFO
botConfig['checkFreq'] = 60

botConfig['version'] = '0.1'

rawConfig = {}

# Check we're not using an old version of Python. Do this before anything else
# We need 2.4 above because some modules (like subprocess) were only introduced in 2.4.
import sys

if int(sys.version_info[1]) <= 3:
    print 'You are using an outdated version of Python. Please update to v2.4 or above (v3 is not supported). For newer OSs, you can update Python without affecting your system install. See http://blog.boxedice.com/2010/01/19/updating-python-on-rhelcentos/ If you are running RHEl 4 / CentOS 4 then you will need to compile Python manually.'
    sys.exit(1)

# Core modules
import ConfigParser
import os
import re
import sched
import time

# After the version check as this isn't available on older Python versions
# and will error before the message is shown
import subprocess

# Custom modules

# Config handling
try:
    path = os.path.realpath(__file__)
    path = os.path.dirname(path)

    config = ConfigParser.ConfigParser()

    if os.path.exists('/etc/mt-bot/config.cfg'):
        configPath = '/etc/mt-bot/config.cfg'
    else:
        configPath = path + '/config.cfg'

    if not os.access(configPath, os.R_OK):
        print 'Unable to read the config file at ' + configPath
        print 'bot will now quit'
        sys.exit(1)

    config.read(configPath)

    # Core config
    botConfig['mt_url'] = config.get('Main', 'mt_url')

    if botConfig['mt_url'].endswith('/'):
        botConfig['mt_url'] = botConfig['mt_url'][:-1]

    botConfig['bot_key'] = config.get('Main', 'bot_key')

    # Tmp path
    if os.path.exists('/var/log/mt-bot/'):
        botConfig['tmpDirectory'] = '/var/log/mt-bot/'
    else:
        botConfig['tmpDirectory'] = '/tmp/' # default which may be overriden in the config later

    botConfig['pidfileDirectory'] = botConfig['tmpDirectory']

    # Plugin config
    if config.has_option('Main', 'plugin_directory'):
        botConfig['pluginDirectory'] = config.get('Main', 'plugin_directory')

    # Optional config
    # Also do not need to be present in the config file (case 28326).
    if config.has_option('Main', 'apache_status_url'):
        botConfig['apacheStatusUrl'] = config.get('Main', 'apache_status_url')

    if config.has_option('Main', 'logging_level'):
        # Maps log levels from the configuration file to Python log levels
        loggingLevelMapping = {
            'debug': logging.DEBUG,
            'info': logging.INFO,
            'error': logging.ERROR,
            'warn': logging.WARN,
            'warning': logging.WARNING,
            'critical': logging.CRITICAL,
            'fatal': logging.FATAL,
            }

        customLogging = config.get('Main', 'logging_level')

        try:
            botConfig['logging'] = loggingLevelMapping[customLogging.lower()]

        except KeyError, ex:
            botConfig['logging'] = logging.INFO

    if config.has_option('Main', 'mongodb_server'):
        botConfig['MongoDBServer'] = config.get('Main', 'mongodb_server')

    if config.has_option('Main', 'mongodb_dbstats'):
        botConfig['MongoDBDBStats'] = config.get('Main', 'mongodb_dbstats')

    if config.has_option('Main', 'mongodb_replset'):
        botConfig['MongoDBReplSet'] = config.get('Main', 'mongodb_replset')

    if config.has_option('Main', 'mysql_server'):
        botConfig['MySQLServer'] = config.get('Main', 'mysql_server')

    if config.has_option('Main', 'mysql_user'):
        botConfig['MySQLUser'] = config.get('Main', 'mysql_user')

    if config.has_option('Main', 'mysql_pass'):
        botConfig['MySQLPass'] = config.get('Main', 'mysql_pass')

    if config.has_option('Main', 'mysql_port'):
        botConfig['MySQLPort'] = config.get('Main', 'mysql_port')

    if config.has_option('Main', 'mysql_socket'):
        botConfig['MySQLSocket'] = config.get('Main', 'mysql_socket')

    if config.has_option('Main', 'nginx_status_url'):
        botConfig['nginxStatusUrl'] = config.get('Main', 'nginx_status_url')

    if config.has_option('Main', 'tmp_directory'):
        botConfig['tmpDirectory'] = config.get('Main', 'tmp_directory')

    if config.has_option('Main', 'pidfile_directory'):
        botConfig['pidfileDirectory'] = config.get('Main', 'pidfile_directory')

    if config.has_option('Main', 'rabbitmq_status_url'):
        botConfig['rabbitMQStatusUrl'] = config.get('Main', 'rabbitmq_status_url')

    if config.has_option('Main', 'rabbitmq_user'):
        botConfig['rabbitMQUser'] = config.get('Main', 'rabbitmq_user')

    if config.has_option('Main', 'rabbitmq_pass'):
        botConfig['rabbitMQPass'] = config.get('Main', 'rabbitmq_pass')

except ConfigParser.NoSectionError, e:
    print 'Config file not found or incorrectly formatted'
    print 'bot will now quit'
    sys.exit(1)

except ConfigParser.ParsingError, e:
    print 'Config file not found or incorrectly formatted'
    print 'bot will now quit'
    sys.exit(1)

except ConfigParser.NoOptionError, e:
    print 'There are some items missing from your config file, but nothing fatal'

# Check to make sure the default config values have been changed (only core config values)
if botConfig['mt_url'] == 'http://example.localhost.com' or botConfig['bot_key'] == 'defaultkey':
    print 'You have not modified config.cfg for your server'
    print 'bot will now quit'
    sys.exit(1)

# Check to make sure sd_url is in correct
if re.match('http(s)?(\:\/\/)[a-zA-Z0-9_\-]+\.(metrics-bot.com)', botConfig['mt_url']) is None:
    print 'Your mt_url is incorrect. It needs to be in the form http://example.metrics-bot.com (or using https)'
    print 'bot will now quit'
    sys.exit(1)

# Check apache_status_url is not empty (case 27073)
if 'apacheStatusUrl' in botConfig and botConfig['apacheStatusUrl'] is None:
    print 'You must provide a config value for apache_status_url. If you do not wish to use Apache monitoring, leave it as its default value - http://www.example.com/server-status/?auto'
    print 'bot will now quit'
    sys.exit(1)

if 'nginxStatusUrl' in botConfig and botConfig['nginxStatusUrl'] is None:
    print 'You must provide a config value for nginx_status_url. If you do not wish to use Nginx monitoring, leave it as its default value - http://www.example.com/nginx_status'
    print 'bot will now quit'
    sys.exit(1)

if 'MySQLServer' in botConfig and botConfig['MySQLServer'] != '' and 'MySQLUser' in botConfig and botConfig[
                                                                                                  'MySQLUser'] != '' and 'MySQLPass' in botConfig:
    try:
        import MySQLdb
    except ImportError:
        print 'You have configured MySQL for monitoring, but the MySQLdb module is not installed. For more info, see: http://www.metrics-bot.com/docs/bot/mysqlstatus/'
        print 'bot will now quit'
        sys.exit(1)

if 'MongoDBServer' in botConfig and botConfig['MongoDBServer'] != '':
    try:
        import pymongo
    except ImportError:
        print 'You have configured MongoDB for monitoring, but the pymongo module is not installed. For more info, see: http://www.metrics-bot.com/docs/bot/mongodbstatus/'
        print 'bot will now quit'
        sys.exit(1)

for section in config.sections():
    rawConfig[section] = {}

    for option in config.options(section):
        rawConfig[section][option] = config.get(section, option)

# Override the generic daemon class to run our checks
class bot(Daemon):
    def run(self):
        mainLogger.debug('Collecting basic system stats')

        # Get some basic system stats to post back for development/testing
        import platform

        systemStats = {'machine': platform.machine(), 'platform': sys.platform, 'processor': platform.processor(),
                       'pythonV': platform.python_version(), 'cpuCores': self.cpuCores()}

        if sys.platform == 'linux2':
            systemStats['nixV'] = platform.dist()

        elif sys.platform == 'darwin':
            systemStats['macV'] = platform.mac_ver()

        elif sys.platform.find('freebsd') != -1:
            version = platform.uname()[2]
            systemStats['fbsdV'] = ('freebsd', version, '') # no codename for FreeBSD

        mainLogger.info('System: ' + str(systemStats))

        mainLogger.debug('Creating checks instance')

        # Checks instance
        c = checks(botConfig, rawConfig, mainLogger)

        # Schedule the checks
        mainLogger.info('checkFreq: %s', botConfig['checkFreq'])
        s = sched.scheduler(time.time, time.sleep)
        c.doChecks(s, True, systemStats) # start immediately (case 28315)
        s.run()

    def cpuCores(self):
        if sys.platform == 'linux2':
            grep = subprocess.Popen(['grep', 'model name', '/proc/cpuinfo'], stdout=subprocess.PIPE, close_fds=True)
            wc = subprocess.Popen(['wc', '-l'], stdin=grep.stdout, stdout=subprocess.PIPE, close_fds=True)
            output = wc.communicate()[0]
            return int(output)

        if sys.platform == 'darwin':
            output =subprocess.Popen(['sysctl', 'hw.ncpu'], stdout=subprocess.PIPE, close_fds=True).communicate()[0].split(':')[
            1]
            return int(output)

# Control of daemon		
if __name__ == '__main__':
    # Logging
    logFile = os.path.join(botConfig['tmpDirectory'], 'mt-bot.log')

    if not os.access(botConfig['tmpDirectory'], os.W_OK):
        print 'Unable to write the log file at ' + logFile
        print 'bot will now quit'
        sys.exit(1)

    handler = logging.handlers.RotatingFileHandler(logFile, maxBytes=10485760, backupCount=5) # 10MB files
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    handler.setFormatter(formatter)

    mainLogger = logging.getLogger('main')
    mainLogger.setLevel(botConfig['logging'])
    mainLogger.addHandler(handler)

    mainLogger.info('--')
    mainLogger.info('mt-bot %s started', botConfig['version'])
    mainLogger.info('--')

    mainLogger.info('mt_url: %s', botConfig['mt_url'])
    mainLogger.info('bot_key: %s', botConfig['bot_key'])

    argLen = len(sys.argv)

    if argLen == 3 or argLen == 4: # needs to accept case when --clean is passed
        if sys.argv[2] == 'init':
            # This path added for newer Linux packages which run under
            # a separate mt-bot user account.
            if os.path.exists('/var/run/mt-bot/'):
                pidFile = '/var/run/mt-bot/mt-bot.pid'
            else:
                pidFile = '/var/run/mt-bot.pid'

    else:
        pidFile = os.path.join(botConfig['pidfileDirectory'], 'mt-bot.pid')

    if not os.access(botConfig['pidfileDirectory'], os.W_OK):
        print 'Unable to write the PID file at ' + pidFile
        print 'bot will now quit'
        sys.exit(1)

    mainLogger.info('PID: %s', pidFile)

    if argLen == 4 and sys.argv[3] == '--clean':
        mainLogger.info('--clean')
        try:
            os.remove(pidFile)
        except OSError:
            # Did not find pid file
            pass

    # Daemon instance from bot class
    daemon = bot(pidFile)

    # Control options
    if argLen == 2 or argLen == 3 or argLen == 4:
        if 'start' == sys.argv[1]:
            mainLogger.info('Action: start')
            daemon.start()

        elif 'stop' == sys.argv[1]:
            mainLogger.info('Action: stop')
            daemon.stop()

        elif 'restart' == sys.argv[1]:
            mainLogger.info('Action: restart')
            daemon.restart()

        elif 'foreground' == sys.argv[1]:
            mainLogger.info('Action: foreground')
            daemon.run()

        elif 'status' == sys.argv[1]:
            mainLogger.info('Action: status')

            try:
                pf = file(pidFile, 'r')
                pid = int(pf.read().strip())
                pf.close()
            except IOError:
                pid = None
            except SystemExit:
                pid = None

            if pid:
                print 'mt-bot is running as pid %s.' % pid
            else:
                print 'mt-bot is not running.'

        elif 'update' == sys.argv[1]:
            mainLogger.info('Action: update')

            if os.path.abspath(__file__) == '/usr/bin/mt-bot/bot.py':
                print 'Please use the Linux package manager that was used to install the bot to update it.'
                print 'e.g. yum install mt-bot or apt-get install mt-bot'
                sys.exit(1)

            import httplib
            import platform
            import urllib2

            print 'Checking if there is a new version';

            # Get the latest version info
            try:
                mainLogger.debug('Update: checking for update')

                request = urllib2.urlopen('http://www.metrics-bot.com/botupdate/')
                response = request.read()

            except urllib2.HTTPError, e:
                print 'Unable to get latest version info - HTTPError = ' + str(e)
                sys.exit(1)

            except urllib2.URLError, e:
                print 'Unable to get latest version info - URLError = ' + str(e)
                sys.exit(1)

            except httplib.HTTPException, e:
                print 'Unable to get latest version info - HTTPException'
                sys.exit(1)

            except Exception, e:
                import traceback

                print 'Unable to get latest version info - Exception = ' + traceback.format_exc()
                sys.exit(1)

            mainLogger.debug('Update: importing json/minjson')

            # We need to return the data using JSON. As of Python 2.6+, there is a core JSON
            # module. We have a 2.4/2.5 compatible lib included with the bot but if we're
            # on 2.6 or above, we should use the core module which will be faster
            pythonVersion = platform.python_version_tuple()

            # Decode the JSON
            if int(pythonVersion[1]) >= 6: # Don't bother checking major version since we only support v2 anyway
                import json

                mainLogger.debug('Update: decoding JSON (json)')

                try:
                    updateInfo = json.loads(response)
                except Exception, e:
                    print 'Unable to get latest version info. Try again later.'
                    sys.exit(1)

            else:
                mainLogger.debug('Update: decoding JSON (minjson)')

            try:
                updateInfo = minjson.safeRead(response)
            except Exception, e:
                print 'Unable to get latest version info. Try again later.'
                sys.exit(1)

            # Do the version check
            if updateInfo['version'] != botConfig['version']:
                import md5 # I know this is depreciated, but we still support Python 2.4 and hashlib is only in 2.5. Case 26918
                import urllib

                print 'A new version is available.'

                def downloadFile(botFile, recursed=False):
                    mainLogger.debug('Update: downloading ' + botFile['name'])
                    print 'Downloading ' + botFile['name']

                    downloadedFile = urllib.urlretrieve(
                        'http://www.metrics-bot.com/downloads/mt-bot/' + botFile['name'])

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
                        if not recursed:
                            downloadFile(botFile, True)

                        else:
                            print botFile[
                                  'name'] + ' did not match its checksum - it is corrupted. This may be caused by network issues so please try again in a moment.'
                            sys.exit(1)

                # Loop through the new files and call the download function
                for botFile in updateInfo['files']:
                    botFile['tempFile'] = downloadFile(botFile)

                    # If we got to here then everything worked out fine. However, all the files are still in temporary locations so we need to move them
                    # This is to stop an update breaking a working bot if the update fails halfway through
                import os
                import shutil # Prevents [Errno 18] Invalid cross-device link (case 26878) - http://mail.python.org/pipermail/python-list/2005-February/308026.html

                for botFile in updateInfo['files']:
                    mainLogger.debug('Update: updating ' + botFile['name'])
                    print 'Updating ' + botFile['name']

                    try:
                        if os.path.exists(botFile['name']):
                            os.remove(botFile['name'])

                        shutil.move(botFile['tempFile'], botFile['name'])

                    except OSError:
                        print 'An OS level error occurred. You will need to manually re-install the bot by downloading the latest version from http://www.metrics-bot.com/downloads/mt-bot.tar.gz. You can copy your config.cfg to the new install'
                        sys.exit(1)

                mainLogger.debug('Update: done')

                print 'Update completed. Please restart the bot (python bot.py restart).'

            else:
                print 'The bot is already up to date'
    else:
        print 'Unknown command'
        sys.exit(1)

    sys.exit(0)

else:
    print 'usage: %s start|stop|restart|status|update' % sys.argv[0]
    sys.exit(1)
