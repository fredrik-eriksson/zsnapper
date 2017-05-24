# zsnapper
ZFS snapshot management for portable clients.

This tool can do three things (in this order):
1. Creates ZFS snapshots at configured intervals
2. Send ZFS snapshots to a remote (or local) backup file system
3. Rotate snapshots after a certain amount of time

I do recommend checking out [sanoid](https://github.com/jimsalterjrs/sanoid) as it's probably more scalable and feature rich. I haven't tried it but wrote this instead because it seemed like fun. Also sanoid wanted a perl dependency, which I would have to install... Oh, and I wanted it to sync automatically to remote automatically, but only if the remote server is available.

## Installation
zsnapper is only tested to be working with python3, but it will probably work in python2 as well (or it should be trivial to fix)

Just install it like any other python module:
```
$ sudo python3 setup.py install
```
Then create your configuration file (for now hard coded to /etc/zsnapper.ini)

zsnapper can then be run from cron, either as root, or as an unprivileged user (see below for details)
```
* * * * * /usr/bin/zsnapper
```

## Configuration
Configuration is done in /etc/zsnapper.ini which, as you might have guessed, is an ini-file. Check the repository zsnapper.ini-sample file for some examples.

To configure snapshotting of a file system you need to create a section for it and add your configuration settings to that section. All configuration settings are applied recursively to all decendant file systems; unless another section overrides them.

Configuration values can be empty, a string, a number or an interval. Interval is simply a number followed by the letter 'd', 'h' or 'm' - as in 'day', 'hour' and 'minute'.

## Running as non-privileged user
Managing ZFS snapshots require root privileges, but if zsnapper is started as a non-privileged user it will attempt to use sudo when executing zfs commands. If sudo is installed you can add these lines to your sudo configuration to allow the backup user to run zsnapper on all file systems in the zpool "tank":
```
backup ALL=(ALL) NOPASSWD: /sbin/zfs snapshot tank*@*
backup ALL=(ALL) NOPASSWD: /sbin/zfs list -H
backup ALL=(ALL) NOPASSWD: /sbin/zfs list -H -t snapshot
backup ALL=(ALL) NOPASSWD: /sbin/zfs destroy tank*@*
# If you use any custom options to zfs send you will need to modify the send commands below
backup ALL=(ALL) NOPASSWD: /sbin/zfs send tank*@*
backup ALL=(ALL) NOPASSWD: /sbin/zfs send -I tank*@* tank*@*
```

If you're sending snapshots over SSH and wants to use an unprivileged user on the remote side (highly recommended) you should add these sudo rules on the remote server:
```
backup ALL= NOPASSWD: /sbin/zfs list -H -t snapshot
# If you use any custom options to zfs receive you will need to modify the receive command
# this will allow the backup user to receive zfs snapshots to anywhere under tank/backup - modify as needed
backup ALL= NOPASSWD: /sbin/zfs receive tank/backup/*
```

## Creating Snapshots
This is the most basic function of this tool. Configuring snapshoting of a file system is easy:
```
[tank]
snapshot_interval=1h
```
This will create snapshots of tank (and all it's children, unless they override the setting) with 1 hours interval. This does not mean the snapshot will be taken at X:00, just that it won't create snapshots more often than once an hour. For example: if the system is started (and the first cron run is) at 09:23 the next snapshot will be created one hour later, at 10:23.

## Syncing Snapshots
Snapshots can be synced either locally or by invoking zfs on a remote system (ssh is the only sane example I can think of, but you can define whatever transport command you want).

A minimal configuration for local snapshot syncing can look like so:
```
[tank]
remote_enable=all
remote_zfs_cmd=/sbin/zfs
remote_zfs_target=backup/tank
```
For an example of remote syncing over ssh, see the zsnapper.ini-sample file.

## Rotating (Weeding) Snapshots
Once new snapshots has been created and synced zsnapper will attempt to weed out old snapshots. Which snapshots to keep is decided by the keep_*-settings. If no such setting is configured all snapshots except the latest are removed.
```
[tank]
weed_enable=1
keep_daily=7
keep_hourly=5
keep_15min=4
```

## Configuration Reference

### snapshot_interval
*default*: unset  
*valid values*: unset, an interval

Interval of file system snapshots. If unset it will not create any snapshots for the file system.

### remote_enable
*default*: unset  
*valid values*: unset, "all", "latest"

If unset the file system will not be sent anywhere. If set to "latest" only the latest snapshot will be sent for incrimental zfs sends (-i flag to zfs send), if set to "all" (or really, any value other than latest) all snapshots newer then the snapshot on the remote side will be sent (-I flag to zfs send).

Note that remote_zfs_cmd and remote_zfs_target must be set as well.

### remote_send_flags
*default*: unset  
*valid values*: unset, space separated flags to zfs send

This can be used if you want to enable any (or all) of the optional flags to zfs send,

### remote_recv_flags
*default*: unset  
*valid values*: unset, space separated flags to zfs receive

This can be used if you want to enable any (or all) of the optional flags to zfs receive,

### remote_zfs_cmd
*default*: unset  
*valid values*: a command to invoke zfs; either local or remote

This option is required when remote_enable is set. The string configured here will actually be a template that you can fill with any other option defined in the section. See sample configuration file for details.

### remote_test_cmd
*default*: unset  
*valid values*: a command that will exit with returncode 0 if it's possible to send snapshots to remote

The test command is run before each snapshot is transferred to the sync location. If the command exits with a non-zero status zsnapper will consider the sync target unavailable and will not attempt to sync the snapshot and an informational message will be written to syslog. This can be used for example to test if the network is available, or if an external backup drive is plugged in or not. I'm sure there are more creative uses as well.

### remote_host
*default*: unset  
*valid values*: any

This setting is completely optional - even when doing remote sync. If present zsnapper will cache the output of 'zfs list -H -t snapshot' on the remote side so it only run once on each remote host. It is also useful to be able to use $(remote_host)s in remote_zfs_cmd.

### remote_zfs_target
*default*: unset  
*valid values*: Location to this file system on the remote side

The file system will be created on the first sync; it must not be created manually.

### weed_enable
*default*: unset  
*valid values*: 1, yes, certainly, anything else

If set snapshot weeding will be done in this file system.

### keep_(yearly,monthly,weekly,daily,hourly,30min,15min,5min,1min,custom)
*default*: 0  
*valid values*: integer

Control which snapshots to remove. Note that while snapshotting is done with a rolling interval, where 1 hour is always at least one hour, the weeding works a bit differently. A yearly snapshot, for example, is only the first snapshot of the year. Monthly is the first snapshot of the month etc. The configured number indicates how many of these snapshots should be saved.

As an example, say that you have snapshots created at 09:43, 13:01, 13:05 and 14:34 and has configured to save 3 hourly snapshots. In this case only the snapshot from 13:05 will be removed since the snapshot from 13:01 is considered the hourly snapshot for that hour. 09:43 is also kept even if it's older than 3 hours since we otherwise would only have 2 hourly snapshots when we wanted 3.

Note that to use keep_custom you also need to define custom_keep_interval.

### custom_keep_interval
*default*: unset  
*valid values*: an interval

custom_keep_interval can be used to create a custom interval other than the pre-defined. Exact use case is pretty much unknown; but it works by counting this interval from EPOCH start and simply create checkpoints with this interval and tries to save snapshots created as soon after those checkpoints as possible. You should probably stick to the pre-defined intervals...

