#!/usr/bin/env python
import logging

# General config
from checks import checks
from daemon import Daemon
import minjson

botConfig = dict()
botConfig['logging'] = logging.INFO
botConfig['checkFreq'] = 60

botConfig['version'] = '0.1'

rawConfig = dict()

# Check we're not using an old version of Python. Do this before anything else
# We need 2.4 above because some modules (like subprocess) were only introduced in 2.4.
import sys

if int(sys.version_info[1]) <= 3:
    print 'You are using an outdated version of Python. Please update to v2.4 or above.'
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


    if config.has_option('Main', 'tmp_directory'):
        botConfig['tmpDirectory'] = config.get('Main', 'tmp_directory')

    if config.has_option('Main', 'pidfile_directory'):
        botConfig['pidfileDirectory'] = config.get('Main', 'pidfile_directory')


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

# Check to make sure mt_url is in correct
if re.match('http(s)?(\:\/\/)[a-zA-Z0-9_\-]+\.(oursite.com)', botConfig['mt_url']) is None:
    print 'Your mt_url is incorrect. It needs to be in the form http://example.oursite.com (or using https)'
    print 'bot will now quit'
    sys.exit(1)


for section in config.sections():
    rawConfig[section] = dict()

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


    else:
        print 'Unknown command'
        sys.exit(1)

    sys.exit(0)

else:
    print 'usage: %s start|stop|restart|status|' % sys.argv[0]
    sys.exit(1)
