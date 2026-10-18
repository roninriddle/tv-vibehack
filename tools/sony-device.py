#!/usr/bin/env python3
"""Install a trial without replacing HOME, and restore its recorded HOME selection."""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import time

ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / '.local'
PACKAGE = 'com.gathin.tvhome'
COMPONENT = PACKAGE + '/.MainActivity'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['backup', 'install-trial', 'start', 'activate', 'restore-home'])
    parser.add_argument('--serial')
    args = parser.parse_args()
    config = STATE / 'device.json'
    serial = args.serial or (json.loads(config.read_text())['serial'] if config.exists() else None)
    if not serial:
        parser.error('--serial must be the current TV IP:wireless-debugging-port')
    adb = STATE / 'tools' / 'platform-tools' / 'adb'
    prefix = [str(adb), '-P', '15037']

    def command(parts, binary=False):
        p = subprocess.run(prefix + ['-s', serial] + parts, capture_output=True,
                           text=not binary, timeout=45)
        if p.returncode:
            raise RuntimeError(p.stderr if not binary else p.stderr.decode(errors='replace'))
        return p.stdout

    def shell(text):
        return command(['shell', text]).strip()

    result = subprocess.run(prefix + ['connect', serial], capture_output=True, text=True, timeout=12)
    if 'connected to' not in result.stdout:
        raise RuntimeError('TV connection unavailable; pass its current wireless debugging address.')
    if shell('getprop ro.product.manufacturer') != 'Sony':
        raise RuntimeError('Connected device is not Sony')
    home_query = ('cmd package resolve-activity --brief --user 0 '
                  '-a android.intent.action.MAIN -c android.intent.category.HOME')
    marker = STATE / 'baseline.json'
    if args.action == 'backup':
        if marker.exists():
            raise RuntimeError('Baseline already exists; keep the original baseline for recovery.')
        home = shell(home_query).splitlines()[-1]
        if not home.startswith('com.dangbei.TVHomeLauncher/'):
            raise RuntimeError('Default HOME changed since inspection; inspect before proceeding.')
        if shell('pm list packages --user 0 ' + PACKAGE):
            raise RuntimeError('Trial package already exists; do not overwrite it without inspection.')
        folder = STATE / 'backups' / datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
        folder.mkdir(parents=True, mode=0o700)
        commands = {
            'packages.txt': 'pm list packages -f --user 0',
            'disabled.txt': 'pm list packages -d --user 0',
            'home.txt': home_query,
            'android.txt': 'getprop ro.build.version.release',
            'firmware.txt': 'getprop ro.boot.vendor.extended_core.sony.build.package.version.display',
        }
        for name, cmd in commands.items():
            dest = folder / name
            dest.write_text(shell(cmd) + '\n')
            dest.chmod(0o600)
        animations = {name: shell('settings get global ' + name) for name in
                      ['window_animation_scale', 'transition_animation_scale', 'animator_duration_scale']}
        baseline = {'created': datetime.datetime.now().isoformat(), 'home': home,
                    'disabled': (folder / 'disabled.txt').read_text().splitlines(),
                    'animations': animations, 'backup': str(folder), 'trial_previously_installed': False}
        marker.write_text(json.dumps(baseline, ensure_ascii=False, indent=2))
        marker.chmod(0o600)
        config.write_text(json.dumps({'serial': serial}))
        config.chmod(0o600)
        (folder / 'screen-before.png').write_bytes(command(['exec-out', 'screencap', '-p'], binary=True))
        print('BASELINE_SAVED; original HOME and package states recorded.')
    elif args.action == 'install-trial':
        baseline = json.loads(marker.read_text())
        if shell(home_query).splitlines()[-1] != baseline['home']:
            raise RuntimeError('Default HOME changed since backup; refusing installation.')
        apk = ROOT / 'outputs' / 'sony-tvhome-trial.apk'
        print(command(['install', '--no-incremental', '-r', str(apk)]).strip())
        for attempt in range(3):
            if shell(home_query).splitlines()[-1] == baseline['home']:
                break
            time.sleep(0.5)
        else:
            raise RuntimeError('HOME selection changed during install; inspect before continuing.')
        print('TRIAL_INSTALLED; original HOME remains selected; SHA256=' + hashlib.sha256(apk.read_bytes()).hexdigest())
    elif args.action == 'start':
        print(shell('am start -n ' + COMPONENT))
    elif args.action == 'activate':
        baseline = json.loads(marker.read_text())
        current = shell(home_query).splitlines()[-1]
        if current != baseline['home'] and not current.startswith(PACKAGE + '/'):
            raise RuntimeError('HOME changed outside this trial; inspect before activating.')
        output = shell('cmd package set-home-activity --user 0 ' + COMPONENT)
        if not shell(home_query).splitlines()[-1].startswith(PACKAGE + '/'):
            raise RuntimeError('Trial HOME selection not verified: ' + output)
        shell('am start -W -n ' + COMPONENT)
        shell('input keyevent 3')
        for attempt in range(10):
            time.sleep(0.5)
            activity = shell('dumpsys activity activities')
            active = [line for line in activity.splitlines() if 'ResumedActivity' in line]
            if any(PACKAGE + '/' in line for line in active):
                break
        else:
            shell('cmd package set-home-activity --user 0 ' + baseline['home'])
            raise RuntimeError('Home key did not open the trial; original HOME restored.')
        print('TRIAL_HOME_ACTIVE; Home key opens trial; original launcher remains installed and enabled.')
    else:
        baseline = json.loads(marker.read_text())
        original = baseline['home']
        # Only restore HOME. Never enable arbitrary packages or reset unrelated settings.
        output = shell('cmd package set-home-activity --user 0 ' + original)
        if shell(home_query).splitlines()[-1] != original:
            raise RuntimeError('HOME restoration not verified: ' + output)
        print(shell('am start -n ' + original))
        print('ORIGINAL_HOME_RESTORED; application data and other settings untouched.')


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print('操作未完成：' + str(error))
        raise SystemExit(1)
