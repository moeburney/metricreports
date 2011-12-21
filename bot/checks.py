

# Core modules
import httplib
import os
import platform
import re
import signal
import subprocess
import sys
import urllib
import urllib2
import minjson

try:
    from hashlib import md5
except ImportError: # Python < 2.5
    from md5 import new as md5

# We need to return the data using JSON. As of Python 2.6+, there is a core JSON
# module. We have a 2.4/2.5 compatible lib included with the bot but if we're
# on 2.6 or above, we should use the core module which will be faster
pythonVersion = platform.python_version_tuple()
python24 = platform.python_version().startswith('2.4')

# Build the request headers
headers = {
    'User-Agent': 'Metrics Bot',
    'Content-Type': 'application/x-www-form-urlencoded',
    'Accept': 'text/html, */*',
    }

if int(pythonVersion[1]) >= 6: # Don't bother checking major version since we only support v2 anyway
    import json
else:
    pass

class checks:
    def __init__(self, botConfig, rawConfig, mainLogger):
        self.botConfig = botConfig
        self.rawConfig = rawConfig
        self.mainLogger = mainLogger
        self.networkTrafficStore = dict()
        self.topIndex = 0
        self.os = None
        self.linuxProcFsLocation = None

        # Set global timeout to 15 seconds for all sockets (case 31033). Should be long enough
        import socket

        socket.setdefaulttimeout(15)


        # Checks






    def getCPUStats(self):
        self.mainLogger.debug('getCPUStats: start')

        cpuStats = dict()

        if sys.platform == 'linux2':
            self.mainLogger.debug('getCPUStats: linux2')

            headerRegexp = re.compile(r'.*?([%][a-zA-Z0-9]+)[\s+]?')
            itemRegexp = re.compile(r'.*?\s+(\d+)[\s+]?')
            valueRegexp = re.compile(r'\d+\.\d+')

            try:
                proc = subprocess.Popen(['mpstat', '-P', 'ALL', '1', '1'], stdout=subprocess.PIPE, close_fds=True)
                stats = proc.communicate()[0]

                if int(pythonVersion[1]) >= 6:
                    try:
                        proc.kill()
                    except Exception, e:
                        self.mainLogger.debug('Process already terminated')

                stats = stats.split('\n')
                header = stats[2]
                headerNames = re.findall(headerRegexp, header)
                device = None

                for statsIndex in range(4, len(stats)): # skip "all"
                    row = stats[statsIndex]

                    if not row: # skip the averages
                        break

                    deviceMatch = re.match(itemRegexp, row)

                    if deviceMatch is not None:
                        device = 'CPU%s' % deviceMatch.groups()[0]

                    values = re.findall(valueRegexp, row.replace(',', '.'))

                    cpuStats[device] = dict()
                    for headerIndex in range(0, len(headerNames)):
                        headerName = headerNames[headerIndex]
                        cpuStats[device][headerName] = values[headerIndex]

            except Exception, ex:
                if int(pythonVersion[1]) >= 6:
                    try:
                        proc.kill()
                    except Exception, e:
                        self.mainLogger.debug('Process already terminated')

                import traceback

                self.mainLogger.error('getCPUStats: exception = ' + traceback.format_exc())
                return False
        else:
            self.mainLogger.debug('getCPUStats: unsupported platform')
            return False

        self.mainLogger.debug('getCPUStats: completed, returning')
        return cpuStats

    def getDiskUsage(self):
        self.mainLogger.debug('getDiskUsage: start')

        # Get output from df
        try:
            try:
                self.mainLogger.debug('getDiskUsage: attempting Popen')

                proc = subprocess.Popen(['df', '-k'], stdout=subprocess.PIPE,
                    close_fds=True) # -k option uses 1024 byte blocks so we can calculate into MB
                df = proc.communicate()[0]

                if int(pythonVersion[1]) >= 6:
                    try:
                        proc.kill()
                    except Exception, e:
                        self.mainLogger.debug('Process already terminated')

            except Exception, e:
                import traceback

                self.mainLogger.error('getDiskUsage: df -k exception = ' + traceback.format_exc())
                return False
        finally:
            if int(pythonVersion[1]) >= 6:
                try:
                    proc.kill()
                except Exception, e:
                    self.mainLogger.debug('Process already terminated')

        self.mainLogger.debug('getDiskUsage: Popen success, start parsing')

        # Split out each volume
        volumes = df.split('\n')

        self.mainLogger.debug('getDiskUsage: parsing, split')

        # Remove first (headings) and last (blank)
        volumes.pop(0)
        volumes.pop()

        self.mainLogger.debug('getDiskUsage: parsing, pop')

        usageData = []

        regexp = re.compile(r'([0-9]+)')

        # Set some defaults
        previousVolume = None
        volumeCount = 0

        self.mainLogger.debug('getDiskUsage: parsing, start loop')

        for volume in volumes:
            self.mainLogger.debug('getDiskUsage: parsing volume: ' + volume)

            # Split out the string
            volume = volume.split(None, 10)

            # Handle df output wrapping onto multiple lines (case 27078 and case 30997)
            # Thanks to http://github.com/sneeu
            if len(volume) == 1: # If the length is 1 then this just has the mount name
                previousVolume = volume[0] # We store it, then continue the for
                continue

            if previousVolume is not None: # If the previousVolume was set (above) during the last loop
                volume.insert(0, previousVolume) # then we need to insert it into the volume
                previousVolume = None # then reset so we don't use it again

            volumeCount += 1

            # Sometimes the first column will have a space, which is usually a system line that isn't relevant
            # e.g. map -hosts              0         0          0   100%    /net
            # so we just get rid of it
            if re.match(regexp, volume[1]) is None:
                pass

            else:
                try:
                    volume[2] = int(volume[2]) / 1024 / 1024 # Used
                    volume[3] = int(volume[3]) / 1024 / 1024 # Available
                except IndexError:
                    self.mainLogger.error('getDiskUsage: parsing, loop IndexError - Used or Available not present')

                except KeyError:
                    self.mainLogger.error('getDiskUsage: parsing, loop KeyError - Used or Available not present')

                usageData.append(volume)

        self.mainLogger.debug('getDiskUsage: completed, returning')

        return usageData

    def getIOStats(self):
        self.mainLogger.debug('getIOStats: start')

        ioStats = dict()

        if sys.platform == 'linux2':
            self.mainLogger.debug('getIOStats: linux2')

            headerRegexp = re.compile(r'([%\\/\-\_a-zA-Z0-9]+)[\s+]?')
            itemRegexp = re.compile(r'^([a-zA-Z0-9\/]+)')
            valueRegexp = re.compile(r'\d+\.\d+')

            try:
                try:
                    proc = subprocess.Popen(['iostat', '-d', '1', '2', '-x', '-k'], stdout=subprocess.PIPE,
                        close_fds=True)
                    stats = proc.communicate()[0]

                    if int(pythonVersion[1]) >= 6:
                        try:
                            proc.kill()
                        except Exception, e:
                            self.mainLogger.debug('Process already terminated')

                    recentStats = stats.split('Device:')[2].split('\n')
                    header = recentStats[0]
                    headerNames = re.findall(headerRegexp, header)
                    device = None

                    for statsIndex in range(1, len(recentStats)):
                        row = recentStats[statsIndex]

                        if not row:
                            # Ignore blank lines.
                            continue

                        deviceMatch = re.match(itemRegexp, row)

                        if deviceMatch is not None:
                            # Sometimes device names span two lines.
                            device = deviceMatch.groups()[0]

                        values = re.findall(valueRegexp, row.replace(',', '.'))

                        if not values:
                            # Sometimes values are on the next line so we encounter
                            # instances of [].
                            continue

                        ioStats[device] = dict()

                        for headerIndex in range(0, len(headerNames)):
                            headerName = headerNames[headerIndex]
                            ioStats[device][headerName] = values[headerIndex]

                except Exception, ex:
                    import traceback

                    self.mainLogger.error('getIOStats: exception = ' + traceback.format_exc())
                    return False
            finally:
                if int(pythonVersion[1]) >= 6:
                    try:
                        proc.kill()
                    except Exception, e:
                        self.mainLogger.debug('Process already terminated')

        else:
            self.mainLogger.debug('getIOStats: unsupported platform')
            return False

        self.mainLogger.debug('getIOStats: completed, returning')
        return ioStats

    def getLoadAvrgs(self):
        self.mainLogger.debug('getLoadAvrgs: start')

        # If Linux like procfs system is present and mounted we use loadavg, else we use uptime
        if sys.platform == 'linux2':
            self.mainLogger.debug('getLoadAvrgs: linux2')

            try:
                self.mainLogger.debug('getLoadAvrgs: attempting open')

                if sys.platform == 'linux2':
                    loadAvrgProc = open('/proc/loadavg', 'r')
                else:
                    loadAvrgProc = open(self.linuxProcFsLocation + '/loadavg', 'r')

                uptime = loadAvrgProc.readlines()

            except IOError, e:
                self.mainLogger.error('getLoadAvrgs: exception = ' + str(e))
                return False

            self.mainLogger.debug('getLoadAvrgs: open success')

            loadAvrgProc.close()

            uptime = uptime[0] # readlines() provides a list but we want a string

        elif sys.platform.find('freebsd') != -1:
            self.mainLogger.debug('getLoadAvrgs: freebsd (uptime)')

            try:
                try:
                    self.mainLogger.debug('getLoadAvrgs: attempting Popen')

                    proc = subprocess.Popen(['uptime'], stdout=subprocess.PIPE, close_fds=True)
                    uptime = proc.communicate()[0]

                    if int(pythonVersion[1]) >= 6:
                        try:
                            proc.kill()
                        except Exception, e:
                            self.mainLogger.debug('Process already terminated')

                except Exception, e:
                    import traceback

                    self.mainLogger.error('getLoadAvrgs: exception = ' + traceback.format_exc())
                    return False
            finally:
                if int(pythonVersion[1]) >= 6:
                    try:
                        proc.kill()
                    except Exception, e:
                        self.mainLogger.debug('Process already terminated')

            self.mainLogger.debug('getLoadAvrgs: Popen success')

        elif sys.platform == 'darwin':
            self.mainLogger.debug('getLoadAvrgs: darwin')

            # Get output from uptime
            try:
                try:
                    self.mainLogger.debug('getLoadAvrgs: attempting Popen')

                    proc = subprocess.Popen(['uptime'], stdout=subprocess.PIPE, close_fds=True)
                    uptime = proc.communicate()[0]

                    if int(pythonVersion[1]) >= 6:
                        try:
                            proc.kill()
                        except Exception, e:
                            self.mainLogger.debug('Process already terminated')

                except Exception, e:
                    import traceback

                    self.mainLogger.error('getLoadAvrgs: exception = ' + traceback.format_exc())
                    return False
            finally:
                if int(pythonVersion[1]) >= 6:
                    try:
                        proc.kill()
                    except Exception, e:
                        self.mainLogger.debug('Process already terminated')

            self.mainLogger.debug('getLoadAvrgs: Popen success')

        elif sys.platform.find('sunos') != -1:
            self.mainLogger.debug('getLoadAvrgs: solaris (uptime)')

            try:
                try:
                    self.mainLogger.debug('getLoadAvrgs: attempting Popen')

                    proc = subprocess.Popen(['uptime'], stdout=subprocess.PIPE, close_fds=True)
                    uptime = proc.communicate()[0]

                    if int(pythonVersion[1]) >= 6:
                        try:
                            proc.kill()
                        except Exception, e:
                            self.mainLogger.debug('Process already terminated')

                except Exception, e:
                    import traceback

                    self.mainLogger.error('getLoadAvrgs: exception = ' + traceback.format_exc())
                    return False
            finally:
                if int(pythonVersion[1]) >= 6:
                    try:
                        proc.kill()
                    except Exception, e:
                        self.mainLogger.debug('Process already terminated')

            self.mainLogger.debug('getLoadAvrgs: Popen success')

        else:
            self.mainLogger.debug('getLoadAvrgs: other platform, returning')
            return False

        self.mainLogger.debug('getLoadAvrgs: parsing')

        # Split out the 3 load average values
        loadAvrgs = [res.replace(',', '.') for res in re.findall(r'([0-9]+[\.,]\d+)', uptime)]
        loadAvrgs = {'1': loadAvrgs[0], '5': loadAvrgs[1], '15': loadAvrgs[2]}

        self.mainLogger.debug('getLoadAvrgs: completed, returning')

        return loadAvrgs

    def getMemoryUsage(self):
        self.mainLogger.debug('getMemoryUsage: start')

        # If Linux like procfs system is present and mounted we use meminfo, else we use "native" mode (vmstat and swapinfo)
        if sys.platform == 'linux2':
            self.mainLogger.debug('getMemoryUsage: linux2')

            try:
                self.mainLogger.debug('getMemoryUsage: attempting open')

                if sys.platform == 'linux2':
                    meminfoProc = open('/proc/meminfo', 'r')
                else:
                    meminfoProc = open(self.linuxProcFsLocation + '/meminfo', 'r')

                lines = meminfoProc.readlines()

            except IOError, e:
                self.mainLogger.error('getMemoryUsage: exception = ' + str(e))
                return False

            self.mainLogger.debug('getMemoryUsage: Popen success, parsing')

            meminfoProc.close()

            self.mainLogger.debug('getMemoryUsage: open success, parsing')

            regexp = re.compile(r'([0-9]+)') # We run this several times so one-time compile now

            meminfo = dict()

            self.mainLogger.debug('getMemoryUsage: parsing, looping')

            # Loop through and extract the numerical values
            for line in lines:
                values = line.split(':')

                try:
                    # Picks out the key (values[0]) and makes a list with the value as the meminfo value (values[1])
                    # We are only interested in the KB data so regexp that out
                    match = re.search(regexp, values[1])

                    if match is not None:
                        meminfo[str(values[0])] = match.group(0)

                except IndexError:
                    break

            self.mainLogger.debug('getMemoryUsage: parsing, looped')

            memData = dict()
            memData['physFree'] = 0
            memData['physUsed'] = 0
            memData['cached'] = 0
            memData['swapFree'] = 0
            memData['swapUsed'] = 0

            # Phys
            try:
                self.mainLogger.debug('getMemoryUsage: formatting (phys)')

                physTotal = int(meminfo['MemTotal'])
                physFree = int(meminfo['MemFree'])
                physUsed = physTotal - physFree

                # Convert to MB
                memData['physFree'] = physFree / 1024
                memData['physUsed'] = physUsed / 1024
                memData['cached'] = int(meminfo['Cached']) / 1024

            # Stops the bot crashing if one of the meminfo elements isn't set
            except IndexError:
                self.mainLogger.error(
                    'getMemoryUsage: formatting (phys) IndexError - Cached, MemTotal or MemFree not present')

            except KeyError:
                self.mainLogger.error(
                    'getMemoryUsage: formatting (phys) KeyError - Cached, MemTotal or MemFree not present')

            self.mainLogger.debug('getMemoryUsage: formatted (phys)')

            # Swap
            try:
                self.mainLogger.debug('getMemoryUsage: formatting (swap)')

                swapTotal = int(meminfo['SwapTotal'])
                swapFree = int(meminfo['SwapFree'])
                swapUsed = swapTotal - swapFree

                # Convert to MB
                memData['swapFree'] = swapFree / 1024
                memData['swapUsed'] = swapUsed / 1024

            # Stops the bot crashing if one of the meminfo elements isn't set
            except IndexError:
                self.mainLogger.error(
                    'getMemoryUsage: formatting (swap) IndexError - SwapTotal or SwapFree not present')

            except KeyError:
                self.mainLogger.error('getMemoryUsage: formatting (swap) KeyError - SwapTotal or SwapFree not present')

            self.mainLogger.debug('getMemoryUsage: formatted (swap), completed, returning')

            return memData

        elif sys.platform.find('freebsd') != -1:
            self.mainLogger.debug('getMemoryUsage: freebsd (native)')

            physFree = None

            try:
                try:
                    self.mainLogger.debug('getMemoryUsage: attempting sysinfo')

                    proc = subprocess.Popen(['sysinfo', '-v', 'mem'], stdout=subprocess.PIPE, close_fds=True)
                    sysinfo = proc.communicate()[0]

                    if int(pythonVersion[1]) >= 6:
                        try:
                            proc.kill()
                        except Exception, e:
                            self.mainLogger.debug('Process already terminated')

                    sysinfo = sysinfo.split('\n')

                    regexp = re.compile(r'([0-9]+)') # We run this several times so one-time compile now

                    for line in sysinfo:
                        parts = line.split(' ')

                        if parts[0] == 'Free':
                            self.mainLogger.debug('getMemoryUsage: parsing free')

                            for part in parts:
                                match = re.search(regexp, part)

                                if match is not None:
                                    physFree = match.group(0)
                                    self.mainLogger.debug('getMemoryUsage: sysinfo: found free %s', physFree)

                        if parts[0] == 'Active':
                            self.mainLogger.debug('getMemoryUsage: parsing used')

                            for part in parts:
                                match = re.search(regexp, part)

                                if match is not None:
                                    physUsed = match.group(0)
                                    self.mainLogger.debug('getMemoryUsage: sysinfo: found used %s', physUsed)

                        if parts[0] == 'Cached':
                            self.mainLogger.debug('getMemoryUsage: parsing cached')

                            for part in parts:
                                match = re.search(regexp, part)

                                if match is not None:
                                    cached = match.group(0)
                                    self.mainLogger.debug('getMemoryUsage: sysinfo: found cached %s', cached)

                except OSError, e:
                    self.mainLogger.debug('getMemoryUsage: sysinfo not available')

                except Exception, e:
                    import traceback

                    self.mainLogger.error('getMemoryUsage: exception = ' + traceback.format_exc())
            finally:
                if int(pythonVersion[1]) >= 6:
                    try:
                        proc.kill()
                    except Exception, e:
                        self.mainLogger.debug('Process already terminated')

            if physFree is None:
                self.mainLogger.info(
                    'getMemoryUsage: sysinfo not installed so falling back on sysctl. sysinfo provides more accurate memory info so is recommended. http://www.freshports.org/sysutils/sysinfo')

                try:
                    try:
                        self.mainLogger.debug('getMemoryUsage: attempting Popen (sysctl)')

                        proc = subprocess.Popen(['sysctl', '-n', 'hw.physmem'], stdout=subprocess.PIPE, close_fds=True)
                        physTotal = proc.communicate()[0]

                        if int(pythonVersion[1]) >= 6:
                            try:
                                proc.kill()
                            except Exception, e:
                                self.mainLogger.debug('Process already terminated')

                        self.mainLogger.debug('getMemoryUsage: attempting Popen (vmstat)')
                        proc = subprocess.Popen(['vmstat', '-H'], stdout=subprocess.PIPE, close_fds=True)
                        vmstat = proc.communicate()[0]

                        if int(pythonVersion[1]) >= 6:
                            try:
                                proc.kill()
                            except Exception, e:
                                self.mainLogger.debug('Process already terminated')

                    except Exception, e:
                        import traceback

                        self.mainLogger.error('getMemoryUsage: exception = ' + traceback.format_exc())

                        return False
                finally:
                    if int(pythonVersion[1]) >= 6:
                        try:
                            proc.kill()
                        except Exception, e:
                            self.mainLogger.debug('Process already terminated')

                self.mainLogger.debug('getMemoryUsage: Popen success, parsing')

                # First we parse the information about the real memory
                lines = vmstat.split('\n')
                physParts = lines[2].split(' ')

                physMem = []

                # We need to loop through and capture the numerical values
                # because sometimes there will be strings and spaces
                for k, v in enumerate(physParts):
                    if re.match(r'([0-9]+)', v) is not None:
                        physMem.append(v)

                physTotal = int(physTotal.strip()) / 1024 # physFree is returned in B, but we need KB so we convert it
                physFree = int(physMem[4])
                physUsed = int(physTotal - physFree)

                self.mainLogger.debug('getMemoryUsage: parsed vmstat')

                # Convert everything to MB
                physUsed = int(physUsed) / 1024
                physFree = int(physFree) / 1024

                cached = 'NULL'

            #
            # Swap memory details
            #

            self.mainLogger.debug('getMemoryUsage: attempting Popen (swapinfo)')

            try:
                try:
                    proc = subprocess.Popen(['swapinfo', '-k'], stdout=subprocess.PIPE, close_fds=True)
                    swapinfo = proc.communicate()[0]

                    if int(pythonVersion[1]) >= 6:
                        try:
                            proc.kill()
                        except Exception, e:
                            self.mainLogger.debug('Process already terminated')

                except Exception, e:
                    import traceback

                    self.mainLogger.error('getMemoryUsage: exception = ' + traceback.format_exc())

                    return False
            finally:
                if int(pythonVersion[1]) >= 6:
                    try:
                        proc.kill()
                    except Exception, e:
                        self.mainLogger.debug('Process already terminated')

            lines = swapinfo.split('\n')
            swapUsed = 0
            swapFree = 0

            for index in range(1, len(lines)):
                swapParts = re.findall(r'(\d+)', lines[index])

                if swapParts != None:
                    try:
                        swapUsed += int(swapParts[len(swapParts) - 3]) / 1024
                        swapFree += int(swapParts[len(swapParts) - 2]) / 1024
                    except IndexError, e:
                        pass

            self.mainLogger.debug('getMemoryUsage: parsed swapinfo, completed, returning')

            return {'physUsed': physUsed, 'physFree': physFree, 'swapUsed': swapUsed, 'swapFree': swapFree,
                    'cached': cached}

        elif sys.platform == 'darwin':
            self.mainLogger.debug('getMemoryUsage: darwin')

            try:
                try:
                    self.mainLogger.debug('getMemoryUsage: attempting Popen (top)')

                    proc = subprocess.Popen(['top', '-l 1'], stdout=subprocess.PIPE, close_fds=True)
                    top = proc.communicate()[0]

                    if int(pythonVersion[1]) >= 6:
                        try:
                            proc.kill()
                        except Exception, e:
                            self.mainLogger.debug('Process already terminated')

                    self.mainLogger.debug('getMemoryUsage: attempting Popen (sysctl)')
                    proc = subprocess.Popen(['sysctl', 'vm.swapusage'], stdout=subprocess.PIPE, close_fds=True)
                    sysctl = proc.communicate()[0]

                    if int(pythonVersion[1]) >= 6:
                        try:
                            proc.kill()
                        except Exception, e:
                            self.mainLogger.debug('Process already terminated')

                except Exception, e:
                    import traceback

                    self.mainLogger.error('getMemoryUsage: exception = ' + traceback.format_exc())
                    return False
            finally:
                if int(pythonVersion[1]) >= 6:
                    try:
                        proc.kill()
                    except Exception, e:
                        self.mainLogger.debug('Process already terminated')

            self.mainLogger.debug('getMemoryUsage: Popen success, parsing')

            # Deal with top
            lines = top.split('\n')
            physParts = re.findall(r'([0-9]\d+)', lines[self.topIndex])

            self.mainLogger.debug('getMemoryUsage: parsed top')

            # Deal with sysctl
            swapParts = re.findall(r'([0-9]+\.\d+)', sysctl)

            self.mainLogger.debug('getMemoryUsage: parsed sysctl, completed, returning')

            return {'physUsed': physParts[3], 'physFree': physParts[4], 'swapUsed': swapParts[1],
                    'swapFree': swapParts[2], 'cached': 'NULL'}

        else:
            self.mainLogger.debug('getMemoryUsage: other platform, returning')
            return False







    def getNetworkTraffic(self):
        self.mainLogger.debug('getNetworkTraffic: start')

        if sys.platform == 'linux2':
            self.mainLogger.debug('getNetworkTraffic: linux2')

            try:
                self.mainLogger.debug('getNetworkTraffic: attempting open')

                proc = open('/proc/net/dev', 'r')
                lines = proc.readlines()

                proc.close()

            except IOError, e:
                self.mainLogger.error('getNetworkTraffic: exception = ' + str(e))
                return False

            self.mainLogger.debug('getNetworkTraffic: open success, parsing')

            columnLine = lines[1]
            _, receiveCols, transmitCols = columnLine.split('|')
            receiveCols = map(lambda a: 'recv_' + a, receiveCols.split())
            transmitCols = map(lambda a: 'trans_' + a, transmitCols.split())

            cols = receiveCols + transmitCols

            self.mainLogger.debug('getNetworkTraffic: parsing, looping')

            faces = dict()
            for line in lines[2:]:
                if line.find(':') < 0: continue
                face, data = line.split(':')
                faceData = dict(zip(cols, data.split()))
                faces[face] = faceData

            self.mainLogger.debug('getNetworkTraffic: parsed, looping')

            interfaces = dict()

            # Now loop through each interface
            for face in faces:
                key = face.strip()

                # We need to work out the traffic since the last check so first time we store the current value
                # then the next time we can calculate the difference
                try:
                    if key in self.networkTrafficStore:
                        interfaces[key] = dict()
                        interfaces[key]['recv_bytes'] = long(faces[face]['recv_bytes']) - long(
                            self.networkTrafficStore[key]['recv_bytes'])
                        interfaces[key]['trans_bytes'] = long(faces[face]['trans_bytes']) - long(
                            self.networkTrafficStore[key]['trans_bytes'])

                        if interfaces[key]['recv_bytes'] < 0:
                            interfaces[key]['recv_bytes'] = long(faces[face]['recv_bytes'])

                        if interfaces[key]['trans_bytes'] < 0:
                            interfaces[key]['trans_bytes'] = long(faces[face]['trans_bytes'])

                        interfaces[key]['recv_bytes'] = str(interfaces[key]['recv_bytes'])
                        interfaces[key]['trans_bytes'] = str(interfaces[key]['trans_bytes'])

                        # And update the stored value to subtract next time round
                        self.networkTrafficStore[key]['recv_bytes'] = faces[face]['recv_bytes']
                        self.networkTrafficStore[key]['trans_bytes'] = faces[face]['trans_bytes']

                    else:
                        self.networkTrafficStore[key] = dict()
                        self.networkTrafficStore[key]['recv_bytes'] = faces[face]['recv_bytes']
                        self.networkTrafficStore[key]['trans_bytes'] = faces[face]['trans_bytes']

                except KeyError, ex:
                    self.mainLogger.error('getNetworkTraffic: no data for %s', key)

                except ValueError, ex:
                    self.mainLogger.error('getNetworkTraffic: invalid data for %s', key)

            self.mainLogger.debug('getNetworkTraffic: completed, returning')

            return interfaces

        elif sys.platform.find('freebsd') != -1:
            self.mainLogger.debug('getNetworkTraffic: freebsd')

            try:
                try:
                    self.mainLogger.debug('getNetworkTraffic: attempting Popen (netstat)')

                    proc = subprocess.Popen(['netstat', '-nbid'], stdout=subprocess.PIPE, close_fds=True)
                    netstat = proc.communicate()[0]

                    if int(pythonVersion[1]) >= 6:
                        try:
                            proc.kill()
                        except Exception, e:
                            self.mainLogger.debug('Process already terminated')

                except Exception, e:
                    import traceback

                    self.mainLogger.error('getNetworkTraffic: exception = ' + traceback.format_exc())

                    return False
            finally:
                if int(pythonVersion[1]) >= 6:
                    try:
                        proc.kill()
                    except Exception, e:
                        self.mainLogger.debug('Process already terminated')

            self.mainLogger.debug('getNetworkTraffic: open success, parsing')

            lines = netstat.split('\n')

            # Loop over available data for each inteface
            faces = dict()
            rxKey = None
            txKey = None

            for line in lines:
                self.mainLogger.debug('getNetworkTraffic: %s', line)

                line = re.split(r'\s+', line)

                # Figure out which index we need
                if rxKey is None and txKey is None:
                    for k, part in enumerate(line):
                        self.mainLogger.debug('getNetworkTraffic: looping parts (%s)', part)

                        if part == 'Ibytes':
                            rxKey = k
                            self.mainLogger.debug('getNetworkTraffic: found rxKey = %s', k)
                        elif part == 'Obytes':
                            txKey = k
                            self.mainLogger.debug('getNetworkTraffic: found txKey = %s', k)

                else:
                    if line[0] not in faces:
                        try:
                            self.mainLogger.debug('getNetworkTraffic: parsing (rx: %s = %s / tx: %s = %s)', rxKey,
                                line[rxKey], txKey, line[txKey])
                            faceData = {'recv_bytes': line[rxKey], 'trans_bytes': line[txKey]}

                            face = line[0]
                            faces[face] = faceData
                        except IndexError, e:
                            continue

            self.mainLogger.debug('getNetworkTraffic: parsed, looping')

            interfaces = dict()

            # Now loop through each interface
            for face in faces:
                key = face.strip()

                try:
                    # We need to work out the traffic since the last check so first time we store the current value
                    # then the next time we can calculate the difference
                    if key in self.networkTrafficStore:
                        interfaces[key] = dict()
                        interfaces[key]['recv_bytes'] = long(faces[face]['recv_bytes']) - long(
                            self.networkTrafficStore[key]['recv_bytes'])
                        interfaces[key]['trans_bytes'] = long(faces[face]['trans_bytes']) - long(
                            self.networkTrafficStore[key]['trans_bytes'])

                        interfaces[key]['recv_bytes'] = str(interfaces[key]['recv_bytes'])
                        interfaces[key]['trans_bytes'] = str(interfaces[key]['trans_bytes'])

                        if interfaces[key]['recv_bytes'] < 0:
                            interfaces[key]['recv_bytes'] = long(faces[face]['recv_bytes'])

                        if interfaces[key]['trans_bytes'] < 0:
                            interfaces[key]['trans_bytes'] = long(faces[face]['trans_bytes'])

                        # And update the stored value to subtract next time round
                        self.networkTrafficStore[key]['recv_bytes'] = faces[face]['recv_bytes']
                        self.networkTrafficStore[key]['trans_bytes'] = faces[face]['trans_bytes']

                    else:
                        self.networkTrafficStore[key] = dict()
                        self.networkTrafficStore[key]['recv_bytes'] = faces[face]['recv_bytes']
                        self.networkTrafficStore[key]['trans_bytes'] = faces[face]['trans_bytes']

                except KeyError, ex:
                    self.mainLogger.error('getNetworkTraffic: no data for %s', key)

                except ValueError, ex:
                    self.mainLogger.error('getNetworkTraffic: invalid data for %s', key)

            self.mainLogger.debug('getNetworkTraffic: completed, returning')

            return interfaces

        else:
            self.mainLogger.debug('getNetworkTraffic: other platform, returning')

            return False



    def getProcesses(self):
        self.mainLogger.debug('getProcesses: start')

        # Get output from ps
        try:
            try:
                self.mainLogger.debug('getProcesses: attempting Popen')

                proc = subprocess.Popen(['ps', 'auxww'], stdout=subprocess.PIPE, close_fds=True)
                ps = proc.communicate()[0]

                if int(pythonVersion[1]) >= 6:
                    try:
                        proc.kill()
                    except Exception, e:
                        self.mainLogger.debug('Process already terminated')

                self.mainLogger.debug('getProcesses: ps result - ' + str(ps))

            except Exception, e:
                import traceback

                self.mainLogger.error('getProcesses: exception = ' + traceback.format_exc())
                return False
        finally:
            if int(pythonVersion[1]) >= 6:
                try:
                    proc.kill()
                except Exception, e:
                    self.mainLogger.debug('Process already terminated')

        self.mainLogger.debug('getProcesses: Popen success, parsing')

        # Split out each process
        processLines = ps.split('\n')

        del processLines[0] # Removes the headers
        processLines.pop() # Removes a trailing empty line

        processes = []

        self.mainLogger.debug('getProcesses: Popen success, parsing, looping')

        for line in processLines:
            self.mainLogger.debug('getProcesses: Popen success, parsing, loop...')
            line = line.replace("'", '') # These will break JSON. ZD38282
            line = line.replace('"', '')
            line = line.split(None, 10)
            processes.append(line)

        self.mainLogger.debug('getProcesses: completed, returning')

        return processes





    def doPostBack(self, postBackData):
        self.mainLogger.debug('doPostBack: start')

        try:
            try:
                self.mainLogger.debug('doPostBack: attempting postback: ' + self.botConfig['mt_url'])

                # Force timeout using signals
                if not python24:
                    signal.signal(signal.SIGALRM, self.signalHandler)
                    signal.alarm(15)

                # Build the request handler
                request = urllib2.Request(self.botConfig['mt_url'] + '/postback/', postBackData, headers)

                # Do the request, log any errors
                response = urllib2.urlopen(request)

                self.mainLogger.info('Postback response: %s', response.read())

            except urllib2.HTTPError, e:
                self.mainLogger.error('doPostBack: HTTPError = %s', e)
                return False

            except urllib2.URLError, e:
                self.mainLogger.error('doPostBack: URLError = %s', e)
                return False

            except httplib.HTTPException, e: # Added for case #26701
                self.mainLogger.error('doPostBack: HTTPException = %s', e)
                return False

            except Exception, e:
                import traceback

                self.mainLogger.error('doPostBack: Exception = ' + traceback.format_exc())
                return False
        finally:
            if not python24:
                signal.alarm(0)

        self.mainLogger.debug('doPostBack: completed')

    def signalHandler(self, signum, frame):
        raise Exception('Signal timeout')

    def doChecks(self, sc, firstRun, systemStats=False):
        macV = None
        if sys.platform == 'darwin':
            macV = platform.mac_ver()

        if not self.topIndex: # We cache the line index from which to read from top
            # Output from top is slightly modified on OS X 10.6+ (case #28239)
            if macV and [int(v) for v in macV[0].split('.')] >= [10, 6, 0]:
                self.topIndex = 6
            else:
                self.topIndex = 5

        if not self.os:
            if macV:
                self.os = 'mac'
            elif sys.platform.find('freebsd') != -1:
                self.os = 'freebsd'
            else:
                self.os = 'linux'

        # We only need to set this if we're on FreeBSD
        if self.linuxProcFsLocation is None and self.os == 'freebsd':
            self.linuxProcFsLocation = self.getMountedLinuxProcFsLocation()
        else:
            self.linuxProcFsLocation = '/proc'

        self.mainLogger.debug('doChecks: start')

        # Do the checks
        diskUsage = self.getDiskUsage()
        loadAvrgs = self.getLoadAvrgs()
        memory = self.getMemoryUsage()
        networkTraffic = self.getNetworkTraffic()
        processes = self.getProcesses()
        ioStats = self.getIOStats();
        cpuStats = self.getCPUStats();

        if len(processes) > 4194304:
            self.mainLogger.warn('doChecks: process list larger than 4MB limit, so it has been stripped')

            processes = []

        self.mainLogger.debug('doChecks: checks success, build payload')

        self.mainLogger.info('doChecks: bot key = ' + self.botConfig['bot_key'])

        checksData = dict()

        # Basic payload items
        checksData['os'] = self.os
        checksData['bot_key'] = self.botConfig['bot_key']
        checksData['botVersion'] = self.botConfig['version']

        if diskUsage:
            checksData['diskUsage'] = diskUsage

        if loadAvrgs:
            checksData['loadAvrg'] = loadAvrgs['1']

        if memory:
            checksData['memPhysUsed'] = memory['physUsed']
            checksData['memPhysFree'] = memory['physFree']
            checksData['memSwapUsed'] = memory['swapUsed']
            checksData['memSwapFree'] = memory['swapFree']
            checksData['memCached'] = memory['cached']

        if networkTraffic:
            checksData['networkTraffic'] = networkTraffic

        if processes:
            checksData['processes'] = processes

        # Apache Status
        if apacheStatus:
            if 'reqPerSec' in apacheStatus:
                checksData['apacheReqPerSec'] = apacheStatus['reqPerSec']

            if 'busyWorkers' in apacheStatus:
                checksData['apacheBusyWorkers'] = apacheStatus['busyWorkers']

            if 'idleWorkers' in apacheStatus:
                checksData['apacheIdleWorkers'] = apacheStatus['idleWorkers']

            self.mainLogger.debug('doChecks: built optional payload apacheStatus')

        # MySQL Status
        if mysqlStatus:
            checksData['mysqlConnections'] = mysqlStatus['connections']
            checksData['mysqlCreatedTmpDiskTables'] = mysqlStatus['createdTmpDiskTables']
            checksData['mysqlMaxUsedConnections'] = mysqlStatus['maxUsedConnections']
            checksData['mysqlOpenFiles'] = mysqlStatus['openFiles']
            checksData['mysqlSlowQueries'] = mysqlStatus['slowQueries']
            checksData['mysqlTableLocksWaited'] = mysqlStatus['tableLocksWaited']
            checksData['mysqlThreadsConnected'] = mysqlStatus['threadsConnected']

            if mysqlStatus['secondsBehindMaster'] is not None:
                checksData['mysqlSecondsBehindMaster'] = mysqlStatus['secondsBehindMaster']

        # Nginx Status
        if nginxStatus:
            checksData['nginxConnections'] = nginxStatus['connections']
            checksData['nginxReqPerSec'] = nginxStatus['reqPerSec']

        # RabbitMQ
        if rabbitmq:
            checksData['rabbitMQ'] = rabbitmq

        # MongoDB
        if mongodb:
            checksData['mongoDB'] = mongodb

        # CouchDB
        if couchdb:
            checksData['couchDB'] = couchdb

        # Plugins
        if plugins:
            checksData['plugins'] = plugins

        if ioStats:
            checksData['ioStats'] = ioStats

        if cpuStats:
            checksData['cpuStats'] = cpuStats

        # Include system stats on first postback
        if firstRun:
            checksData['systemStats'] = systemStats
            self.mainLogger.debug('doChecks: built optional payload systemStats')

        # Include server indentifiers
        import socket

        try:
            checksData['internalHostname'] = socket.gethostname()
            self.mainLogger.info('doChecks: hostname = ' + checksData['internalHostname'])

        except socket.error, e:
            self.mainLogger.debug('Unable to get hostname: ' + str(e))

        self.mainLogger.debug('doChecks: payload: %s' % checksData)
        self.mainLogger.debug('doChecks: payloads built, convert to json')

        # Post back the data
        if int(pythonVersion[1]) >= 6:
            self.mainLogger.debug('doChecks: json convert')

            payload = json.dumps(checksData)
            testobj = json.loads(payload)

        else:
            self.mainLogger.debug('doChecks: minjson convert')

            payload = minjson.write(checksData)
            testobj = minjson.read(payload)

        self.mainLogger.debug('doChecks: json converted, hash')

        payloadHash = md5(payload).hexdigest()
        postBackData = urllib.urlencode({'payload': payload, 'hash': payloadHash})

        self.mainLogger.debug('doChecks: hashed, doPostBack')

        self.doPostBack(postBackData)

        self.mainLogger.debug('doChecks: posted back, reschedule')

        sc.enter(self.botConfig['checkFreq'], 1, self.doChecks, (sc, False))

    def getMountedLinuxProcFsLocation(self):
        self.mainLogger.debug('getMountedLinuxProcFsLocation: attempting to fetch mounted partitions')

        # Lets check if the Linux like style procfs is mounted
        try:
            proc = subprocess.Popen(['mount'], stdout=subprocess.PIPE, close_fds=True)
            mountedPartitions = proc.communicate()[0]

            if int(pythonVersion[1]) >= 6:
                try:
                    proc.kill()
                except Exception, e:
                    self.mainLogger.debug('Process already terminated')

            location = re.search(r'linprocfs on (.*?) \(.*?\)', mountedPartitions)

        except OSError, e:
            self.mainLogger.error('getMountedLinuxProcFsLocation: OS error: ' + str(e))

        # Linux like procfs file system is not mounted so we return False, else we return mount point location
        if location is None:
            self.mainLogger.debug('getMountedLinuxProcFsLocation: none found so using /proc')
            return '/proc' # Can't find anything so we might as well try this

        location = location.group(1)

        self.mainLogger.debug('getMountedLinuxProcFsLocation: using' + location)

        return location
