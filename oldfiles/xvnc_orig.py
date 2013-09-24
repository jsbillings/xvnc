#!/usr/bin/env python
#
#  Xvnc Report Generator.
#
import os
import re
import sys
import time
from datetime import timedelta

# RE information ***
XVNC_START_RE  = re.compile('(?P<date>\d+) (?P<logtime>\d\d:\d\d:\d\d) (?P<host>caen-vnc[^.]+\.engin\.umich\.edu) pam: gdm-password\[(?P<pid>\d+).*pam_unix\(gdm-password:session\): session opened for user (?P<userid>\w+) by')
XVNC_CLOSED_RE = re.compile('(?P<date>\d+) (?P<logtime>\d\d:\d\d:\d\d) (?P<host>caen-vnc[^.]+\.engin\.umich\.edu) pam: gdm-password\[(?P<pid>\d+).*pam_unix\(gdm-password:session\): session closed for user (?P<userid>\w+)')

# secs2HHMMSS
def secs2HHMMSS( seconds ):
  """ converts integer seconds into a time string, HH:MM:SS.
  """
  hrs = seconds / 3600
  secs = seconds  % 3600
  mins = secs / 60
  secs = secs % 60
  return "%02d:%02d:%02d" % ( hrs, mins, secs)

# pidIndex
def pidIndex ( deltaTs, pid ):
  """
    return 1st delta time array index with matching "pid".
  """
  i=0
  for t in deltaTs:
    if t[2] == pid:
      return i
    i = i + 1
  return -1

# calcTotalSessionTime
def calcTotalSessionTime( startTs, endTs):
  """
    Calculate total sesion time given an array of Start & End Times.
    
    """
  enddeltas=[]
  startdeltas=[]
  for startt in startTs:
    t= time.strptime( startt[0],  "%H:%M:%S")
    pid = startt[2]
    startdeltas.append( [ timedelta(hours=t.tm_hour, minutes=t.tm_min, seconds=t.tm_sec), startt[1], pid ] )
  for endt in endTs:
    t= time.strptime( endt[0],  "%H:%M:%S")
    pid = endt[2]
    enddeltas.append( [ timedelta(hours=t.tm_hour, minutes=t.tm_min, seconds=t.tm_sec), endt[1], pid ] )
  zeroT  = timedelta( hours=0, minutes=0, seconds=0)
  TotalT = timedelta( hours=0, minutes=0, seconds=0)
  # WARNING: Assumes cron caentasks.daily is being run at 23:21:00
  T2320 = timedelta( hours=23, minutes=20, seconds=0)
  # only   start time(s) ?
  if len(startdeltas) > 0 and len(enddeltas) == 0:
    startt = startdeltas.pop(0)
    while startt:
      if startt[0] < T2320:
        TotalT = TotalT + (T2320 - startt[0])
      else:
        TotalT = TotalT + ( timedelta(hours=23, minutes=59, seconds=60) - startt[0] )
      try:
        startt = startdeltas.pop(0)
      except IndexError:
        break
    return TotalT
  # only end time(s) ?
  elif len(startdeltas) == 0 and len(enddeltas) > 0:
    endt = enddeltas.pop(0)
    while endt:
      if endt[0] <= T2320:
        TotalT = TotalT + endt[0]
      else:
        TotalT = TotalT + (endt[0] - T2320)
      try:
        endt = enddeltas.pop(0)
      except IndexError:
        break
    return TotalT
  else:
    endt=False
    startt = startdeltas.pop(0)
    while( startt ):
      pid = startt[2]
      i = pidIndex( enddeltas, pid )
      if i == -1:
        # start time but no matching end time, session must have finished the next day?
        if startt[0] < T2320:
          TotalT = TotalT + ( T2320 - startt[0] )
        else:
          TotalT = TotalT + ( timedelta(hours=23, minutes=59, seconds=60) - startt[0] )
      else:
        endt = enddeltas.pop( i )
        #  end > start time & days the same ??
        if (endt[0] - startt[0]) > zeroT and endt[1] == startt[1]:
          # normal pairing of start and end session times
          nt = endt[0] - startt[0]
          TotalT = TotalT + nt
          endt = False
        else:
          #  session started previous day
          TotalT = TotalT + ( timedelta(hours=23, minutes=59, seconds=60) - startt[0] ) 
          TotalT = TotalT + endt[0]
          endt = False
      try:
        startt = startdeltas.pop(0)
      except IndexError:
        break
      continue
  while endt:
    if endt[0] <= T2320:
      TotalT = TotalT + endt[0]
    else:
      TotalT = TotalT + (endt[0] - T2320)
    try:
      endt = enddeltas.pop(0)
    except IndexError:
      break
  return TotalT

# Main Program ***
Logins = {}
Users = {}
for line in sys.stdin.readlines():
  m = XVNC_START_RE.search( line )
  if m:
    pid=m.group("pid")
    host = m.group("host")
    userid = m.group("userid")
    if not Logins.has_key( host ):
      Logins[ host ] = {}
    if not Logins[ host ].has_key( userid ):
      Logins[ host ][ userid ] = [ 1, [ [ m.group("logtime"),m.group("date"),pid ] ], [] ]
    else:
      Logins[ host ][ userid ][0]  += 1
      Logins[ host ][ userid ][1].append( [ m.group("logtime"),m.group("date"),pid ] )

    # sum up sessions for unique "userid" across all login hosts
    if not Users.has_key( userid ):
      Users[ userid ] = [ 1 ]
    else:
      Users[ userid ][ 0 ] += 1

  m = XVNC_CLOSED_RE.search( line )
  if m:
    pid=m.group("pid")
    host = m.group("host")
    userid = m.group("userid")
    if not Logins.has_key( host ):
      Logins[ host ] = {}
    if not Logins[ host ].has_key( userid ):
      Logins[ host ][ userid ] = [ 1, [], [ [ m.group("logtime"),m.group("date"),pid ] ] ] 
    else:
      Logins[ host ][ userid ][2].append( [ m.group("logtime"),m.group("date"),pid ] )

    # may not be a session start time for this user ?
    if not Users.has_key( userid ):
      Users[ userid ] = [ 1 ]


nTunique = len(Users)

# sum up total session time and session count for all users across all hosts
for host in sorted(Logins.keys()):
   for user in sorted(Logins[host].keys()):
     totalT = calcTotalSessionTime( Logins[host][user][1], Logins[host][user][2] )
     nsessions = Logins[ host ][ user ][0]
     try:
       Users[ user ][ 1 ] += totalT
       Users[ user ][ 2 ] += nsessions
     except IndexError:
       Users[ user ].append( totalT )
       Users[ user ].append( nsessions )

totalsessions = 0
totalTsecs = 0
for host in sorted(Logins.keys()):
   sys.stdout.write("%s:\n" % host)
   nsessions = 0
   totalHostTsecs = 0
   nunique = 0
   for user in sorted(Logins[host].keys()):
     n = Logins[host][user][0]
     totalT = calcTotalSessionTime( Logins[host][user][1], Logins[host][user][2] )
     nunique += 1
     nsessions += n
     totalsessions += n
     totalTsecs = totalTsecs + totalT.seconds
     totalHostTsecs = totalHostTsecs + totalT.seconds
     ntotal = Users[ user ][ 2 ]
     sys.stdout.write("    %s: %d( all hosts: %d )  %s( all  hosts: %s )\n" % (user,
                                                            n,
                                                            ntotal,
                                                            secs2HHMMSS(totalT.seconds),
                                                            secs2HHMMSS(Users[user][1].seconds)) )

   sys.stdout.write("    ---------------------\n")
   sys.stdout.write("    Total of %d Xvnc sessions, %s(HHH:MM:SS), for %d unique users.\n\n" % (nsessions,
												secs2HHMMSS(totalHostTsecs),
												nunique) )

sys.stdout.write("---------------------\n")
sys.stdout.write("Total of %d Xvnc sessions, %s(HHH:MM:SS), for %d unique users.\n" % (totalsessions,
                                                                                     secs2HHMMSS(totalTsecs),
                                                                                     nTunique) )
sys.exit(0)
