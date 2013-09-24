#!/usr/bin/env python

import os, sys, time, re, datetime

class xvnc_Generator(object):
    regEx = re.compile('(?P<month>\w+) (?P<day>\d+) (?P<logtime>\d\d:\d\d:\d\d) (?P<host>caen-vnc[^.]+\.engin\.umich\.edu) sshd\[(?P<pid>\d+)\]: pam_unix\(sshd:session\): session (?P<action>\w+) for user (?P<user>\w+)')

    def __init__(self):
        self.logins = {}
        self.users = {}
        self.start = 0
        self.end = 0

    def readLine(self, line):
        m = self.regEx.search(line)
        if m: self.addExp(m)

    def addExp(self, m):
        month = m.group('month')
        day = m.group('day')
        logtime = m.group('logtime')
        host = m.group('host')
        try:
            pid = int(m.group('pid'))
        except TypeError:
            pid = m.group('pid')
            sys.stderr.write('Error in logs: %s is not a valid pid.\n' % pid)
        action = m.group('action')
        user = m.group('user')
        try:
            timeEp = time.mktime(time.strptime('%s %s %s %s' % (month, day, time.localtime(time.time()).tm_year, logtime), '%b %d %Y %H:%M:%S'))
        except Exception:
            sys.stderr.write('Error in logs: unable to parse time (%s %s %s).\n'
                             % (month, day, logtime))
        if not self.start:
            self.start = timeEp
        self.end = timeEp
        if action == 'opened':
            if self.openSess(host, pid, timeEp):
                self.addUser(user)
        elif action == 'closed':
            if self.closeSess(host, pid, timeEp):
                self.addUser(user)

    def openSess(self, host, pid, timeEp):
        if not self.logins.has_key(host):
            self.logins[host] = {'pids': {}, 'sessions': 0, 'totTime': 0}
        if not self.logins[host]['pids'].has_key(pid):
            self.logins[host]['pids'][pid] = [ 1, [{'start': timeEp, 
                                                    'end': False, 
                                                    'active': True}]]
            self.logins[host]['sessions'] += 1
        else:
            for item in self.logins[host]['pids'][pid][1]:
                if item['active']:
                    sys.stderr.write('Error in logs: pid (%s) already active.\n' % pid)
                    return False;
            self.logins[host]['pids'][pid][0] += 1
            self.logins[host]['pids'][pid][1].append({'start': timeEp, 'end': False, 'active': True})
            self.logins[host]['sessions'] += 1
        return True;

    def closeSess(self, host, pid, timeEp):
        if not self.logins.has_key(host):
            self.logins[host] = {'pids': {}, 'sessions': 0, 'totTime': 0}
        if not self.logins[host]['pids'].has_key(pid):
            self.logins[host]['pids'][pid] = [ 1, [{'start': False, 
                                                    'end': timeEp, 
                                                    'active': False}]]
            self.logins[host]['sessions'] += 1
        else:
            for item in self.logins[host]['pids'][pid][1]:
                if item['active']:
                    item['active'] = False
                    item['end'] = timeEp
                    self.logins[host]['totTime'] += item['end'] - item['start']
                    return False;
            sys.stderr.write('Error in logs: pid (%s) already closed.\n' % pid)
            return False;
        return True;

    def addUser(self, user):
        if not self.users.has_key(user):
            self.users[user] = 1;
        else:
            self.users[user] += 1

    def closeLogs(self):
        for host in self.logins.iterkeys():
            for pid in self.logins[host]['pids'].iterkeys():
                for item in self.logins[host]['pids'][pid][1]:
                    if item['active']:
                        self.logins[host]['totTime'] += self.end - item['start']

################################################################################

def secs2HHMMSS( seconds ):
  """ converts integer seconds into a time string, HH:MM:SS.
  """
  hrs = seconds / 3600
  secs = seconds  % 3600
  mins = secs / 60
  secs = secs % 60
  return "%02d:%02d:%02d" % ( hrs, mins, secs)       
        

################################################################################
# Main Program

reports = xvnc_Generator()
for line in sys.stdin.readlines():
    reports.readLine(line)

reports.closeLogs()

print '\n Report Log Summary:\n'
print ' %-39.39s %38.38s' % (('Start: %s' % time.asctime(time.localtime(reports.start))), ('End: %s' % time.asctime(time.localtime(reports.end))))
print ' %s ' % ('-' * 78)
print
print '\tHost                 Sessions Total Login Time Avg Login Time'
print '\t-------------------- -------- ---------------- --------------'
for host in sorted(reports.logins.keys()):
    print '\t%-20.20s %8d %16.16s %14.14s' % (host, reports.logins[host]['sessions'], secs2HHMMSS(reports.logins[host]['totTime']), secs2HHMMSS(reports.logins[host]['totTime']/float(reports.logins[host]['sessions'])))
print
print

numSess = 0

for user in reports.users.iterkeys():
    numSess += reports.users[user]

print '\tTotal number of unique users: %d\n\tTotal number of sessions: %d\n' % (len(reports.users.keys()), numSess)
print ' %s ' % ('-' * 78)
