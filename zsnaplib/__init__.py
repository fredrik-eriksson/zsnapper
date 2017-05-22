import datetime
import logging
import re
import subprocess
import sys

time_format='%Y-%m-%d_%H%M'
zfs_bin='/sbin/zfs'
sudo_bin='/usr/bin/sudo'
re_snapshot = re.compile(r'^(.*)@([0-9]{4}-[0-9]{2}-[0-9]{2}_[0-9]{4})$')
logger = 'zsnapper'

class ZFSSnapshotError(Exception):
    pass

def do_zfs_command(args, sudo, pipecmd=None, zfs_cmd=[zfs_bin]):
    cmd = []
    sudopw = None
    if sudo:
        cmd.append(sudo_bin)
        if sys.version_info[0] == 3:
            if isinstance(sudo, str):
                cmd.append('--stdin')
                sudopw = '{}\n'.format(sudo)
        elif isinstance(sudo, basestring):
            cmd.append('--stdin')
            sudopw = '{}\n'.format(sudo)

    cmd.extend(zfs_cmd)
    cmd.extend(args)
    proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)
    ctrl_proc = proc
    if pipecmd:
        proc2 = subprocess.Popen(
                pipecmd,
                stdin=proc.stdout,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE)
        proc.stdout.close()
        ctrl_proc = proc2

    (out, err) = ctrl_proc.communicate()

    if ctrl_proc.returncode != 0:
        print(proc.returncode)
        raise ZFSSnapshotError('Failed to execute {}: {}'.format(cmd, err))
    return out

def send_snapshot(
        fs, 
        snap, 
        remote_zfs_cmd, 
        remote_target,
        sudo=False, 
        send_opts=[],
        recv_opts=[], 
        repl_mode='all',
        repl_from=None):
    snap = snap.strftime(time_format)
    if repl_from:
        if repl_mode == 'latest':
            inc_flag = '-i'
        else:
            inc_flag = '-I'

        repl_from = repl_from.strftime(time_format)
        args = [ 'send' ] + send_opts + [ inc_flag, '{}@{}'.format(fs, repl_from), '{}@{}'.format(fs, snap) ]
    else:
        args = [ 'send', '{}@{}'.format(fs, snap) ]

    pipecmd = remote_zfs_cmd + [ 'receive' ] + recv_opts + [ remote_target ]

    do_zfs_command(args, sudo, pipecmd=pipecmd)


def create_snapshot(fs, sudo=False):

    d = datetime.datetime.now().strftime(time_format)
    args = ['snapshot', '{}@{}'.format(fs, d)]
    do_zfs_command(args, sudo)

def get_filesystems(sudo=False, zfs_cmd=[zfs_bin]):
    args = ['list', '-H']
    out = do_zfs_command(args, sudo, zfs_cmd=zfs_cmd)
    ret = set()

    for row in out.splitlines():
        row = row.decode('UTF-8')
        ret.add(row.split()[0])
    return ret


def get_snapshots(sudo=False, zfs_cmd=[zfs_bin]):
    args = [ 'list', '-H', '-t', 'snapshot' ]
    out = do_zfs_command(args, sudo, zfs_cmd=zfs_cmd)
    snapshots = {}

    for row in out.splitlines():
        row = row.decode('UTF-8').split()[0]
        res = re_snapshot.match(row)
        if res:
            d = datetime.datetime.strptime(res.group(2), time_format)
            if res.group(1) in snapshots:
                snapshots[res.group(1)].append(d)
            else:
                snapshots[res.group(1)] = [d]

    for l in snapshots.values():
        l.sort(reverse=True)

    return snapshots


def remove_snapshot(fs, date, sudo=False):
    date = date.strftime(time_format)
    args = [ 'destroy', '{}@{}'.format(fs, date) ]
    do_zfs_command(args, sudo)


def weed_snapshots(
        fs,
        dates,
        custom_keep_interval = None,
        keep_custom = 0,
        keep_yearly = 0,
        keep_monthly = 0,
        keep_weekly = 0,
        keep_daily = 0,
        keep_hourly = 0,
        keep_30min = 0,
        keep_15min = 0,
        keep_5min = 0,
        keep_1min = 0,
        sudo = False):

    log = logging.getLogger(logger)

    keep = {
            'custom': [],
            'year' : [],
            'month' : [],
            'week' : [],
            'day' : [],
            'hour' : [],
            'min30' : [],
            'min15' : [],
            'min5' : [],
            'min1' : []
            }
    saved = {
            'custom': [],
            'year' : [],
            'month' : [],
            'week' : [],
            'day' : [],
            'hour' : [],
            'min30' : [],
            'min15' : [],
            'min5' : [],
            'min1' : []
            }

    for date in sorted(dates):
        min1 = date-datetime.timedelta(seconds=date.second, microseconds=date.microsecond)
        min5 = date-datetime.timedelta(minutes=date.minute%5, seconds=date.second, microseconds=date.microsecond)
        min15 = date-datetime.timedelta(minutes=date.minute%15, seconds=date.second, microseconds=date.microsecond)
        min30 = date-datetime.timedelta(minutes=date.minute%30, seconds=date.second, microseconds=date.microsecond)
        hour = date-datetime.timedelta(minutes=date.minute, seconds=date.second, microseconds=date.microsecond)
        day = datetime.datetime.combine(date.date(), datetime.time.min)
        week = datetime.datetime.combine(date.date()-datetime.timedelta(days=date.weekday()), datetime.time.min)
        month = datetime.datetime(year=date.year, month=date.month, day=1)
        year = datetime.datetime(year=date.year, month=1, day=1)
        # yearly snapshots
        if year not in saved['year']:
            saved['year'].append(year)
            keep['year'].append(date)
        if month not in saved['month']:
            saved['month'].append(month)
            keep['month'].append(date)
        if week not in saved['week']:
            saved['week'].append(week)
            keep['week'].append(date)
        if day not in saved['day']:
            saved['day'].append(day)
            keep['day'].append(date)
        if hour not in saved['hour']:
            saved['hour'].append(hour)
            keep['hour'].append(date)
        if min30 not in saved['min30']:
            saved['min30'].append(min30)
            keep['min30'].append(date)
        if min15 not in saved['min15']:
            saved['min15'].append(min15)
            keep['min15'].append(date)
        if min5 not in saved['min5']:
            saved['min5'].append(min5)
            keep['min5'].append(date)
        if min1 not in saved['min1']:
            saved['min1'].append(min1)
            keep['min1'].append(date)

        if custom_keep_interval:
            cur = year
            while cur+custom_keep_interval < date:
                cur += custom_keep_interval
            if cur not in saved['custom']:
                saved['custom'].append(cur)
                keep['custom'].append(date)

    if keep_yearly:
        saved['year'] = saved['year'][-keep_yearly:]
    else:
        saved['year'] = []
    
    if keep_monthly:
        saved['month'] = saved['month'][-keep_monthly:]
    else:
        saved['month'] = []

    if keep_weekly:
        saved['week'] = saved['week'][-keep_weekly:]
    else:
        saved['week'] = []

    if keep_daily:
        saved['day'] = saved['day'][-keep_daily:]
    else:
        saved['day'] = []

    if keep_hourly:
        saved['hour'] = saved['hour'][-keep_hourly:]
    else:
        saved['hour'] = []

    if keep_30min:
        saved['min30'] = saved['min30'][-keep_30min:]
    else:
        saved['min30'] = []

    if keep_15min:
        saved['min15'] = saved['min15'][-keep_15min:]
    else:
        saved['min15'] = []

    if keep_5min:
        saved['min5'] = saved['min5'][-keep_5min:]
    else:
        saved['min5'] = []

    if keep_1min:
        saved['min1'] = saved['min1'][-keep_1min:]
    else:
        saved['min1'] = []

    if keep_custom:
        saved['custom'] = saved['custom'][-keep_custom:]
    else:
        saved['custom'] = []

    all_saved = []
    all_saved.extend(saved['year'])
    all_saved.extend(saved['month'])
    all_saved.extend(saved['week'])
    all_saved.extend(saved['day'])
    all_saved.extend(saved['hour'])
    all_saved.extend(saved['min30'])
    all_saved.extend(saved['min15'])
    all_saved.extend(saved['min5'])
    all_saved.extend(saved['min1'])
    all_saved.extend(saved['custom'])
    all_saved = set(all_saved)

    to_remove = [date for date in dates if date not in all_saved]
    for date in to_remove:
        try:
            log.info('{}: removing snapshot from {}'.format(fs, date))
            remove_snapshot(fs, date, sudo=sudo)
        except ZFSSnapshotError as e:
            log.error(str(e))



