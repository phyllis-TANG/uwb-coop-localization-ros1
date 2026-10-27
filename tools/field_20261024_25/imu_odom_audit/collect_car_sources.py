#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Python2/3 source/provenance capture; no ROS/serial/control initialization.

Run on the selected car. Writes only a NEW requested evidence archive. Source
files and active executables are read/hashed, never compiled or executed.
"""
from __future__ import print_function
import argparse
import datetime
import hashlib
import io
import json
import os
import platform
import struct
import tarfile


def digest(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        while True:
            chunk=f.read(1048576)
            if not chunk:break
            h.update(chunk)
    return h.hexdigest()


def active_nodes():
    result=[]
    for entry in os.listdir('/proc'):
        if not entry.isdigit():continue
        try:
            raw=open('/proc/'+entry+'/cmdline','rb').read().split(b'\0')[0]
            name=os.path.basename(raw.decode('utf-8','replace'))
            if name not in ('wheeltec_robot_node','robot_pose_ekf'):continue
            exe='/proc/'+entry+'/exe'
            result.append(dict(pid=int(entry),executable=os.readlink(exe),sha256=digest(exe)))
        except (IOError,OSError):continue
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--car',required=True,choices=['car1','car2'])
    p.add_argument('--package',default='/home/wheeltec/wheeltec_robot/src/turn_on_wheeltec_robot')
    p.add_argument('--output',required=True)
    args=p.parse_args()
    package=os.path.realpath(args.package);output=os.path.abspath(os.path.expanduser(args.output))
    if os.path.exists(output):raise ValueError('output exists; choose a NEW evidence filename')
    if not os.path.isdir(package):raise ValueError('package not found; supply observed actual --package path')
    files=[]
    for folder in ('src','include','launch'):
        base=os.path.join(package,folder)
        if not os.path.isdir(base):continue
        for parent,dirs,names in os.walk(base):
            dirs[:]=[n for n in dirs if not os.path.islink(os.path.join(parent,n))]
            for name in names:
                path=os.path.join(parent,name)
                if not os.path.islink(path) and name.endswith(('.cpp','.c','.h','.hpp','.launch','.urdf','.xacro')):files.append(path)
    for name in ('CMakeLists.txt','package.xml'):
        path=os.path.join(package,name)
        if os.path.isfile(path) and not os.path.islink(path):files.append(path)
    if not files:raise ValueError('no selected source files')
    metadata=dict(car=args.car,captured_utc=datetime.datetime.utcnow().isoformat()+'Z',
        machine=platform.machine(),kernel=platform.release(),python=platform.python_version(),
        native_long_bits=struct.calcsize('l')*8,package_path=package,
        current_source_capture_only=True,historical_deployment_proved=False,
        active_node_binaries=active_nodes(),
        files={os.path.relpath(path,package):dict(sha256=digest(path),size_bytes=os.path.getsize(path)) for path in sorted(files)},
        operations='read/hash selected files and /proc executable identity; write only new archive; no source execution, ROS, serial, sudo or motion')
    payload=(json.dumps(metadata,ensure_ascii=False,indent=2)+'\n').encode('utf-8')
    # O_EXCL prevents accidental overwrite, including a repeated pasted command.
    fd=os.open(output,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'wb') as fileobj:
        with tarfile.open(fileobj=fileobj,mode='w:gz') as archive:
            for path in sorted(files):archive.add(path,arcname='source/'+os.path.relpath(path,package),recursive=False)
            info=tarfile.TarInfo('capture.json');info.size=len(payload)
            archive.addfile(info,io.BytesIO(payload))
    print(json.dumps(dict(status='CAPTURED',car=args.car,archive=output,sha256=digest(output),
        source_files=len(files),active_binary_count=len(metadata['active_node_binaries']),historical_deployment_proved=False)))


if __name__=='__main__':main()
