#!/usr/bin/env python3
"""Short, repeatable launcher navigation sample; not a sustained benchmark."""
import argparse
import json
from pathlib import Path
import subprocess
import time

ROOT = Path(__file__).resolve().parent.parent


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('label')
    args = parser.parse_args()
    state = ROOT / '.local'
    serial = json.loads((state / 'device.json').read_text())['serial']
    base = [str(state / 'tools/platform-tools/adb'), '-P', '15037', '-s', serial]

    def shell(cmd):
        p = subprocess.run(base + ['shell', cmd], capture_output=True, text=True, timeout=20)
        if p.returncode:
            raise RuntimeError(p.stderr)
        return p.stdout

    shell('am force-stop com.gathin.tvhome')
    shell('am start -W -n com.gathin.tvhome/.MainActivity')
    time.sleep(1)
    result = {'label': args.label, 'display': shell('wm size; wm density')}
    result['memory_idle'] = shell('dumpsys meminfo com.gathin.tvhome')
    pid = shell('pidof com.gathin.tvhome').strip().split()[0]
    result['cpu_idle'] = shell('top -b -n 3 -d 1 -p ' + pid)
    shell('dumpsys gfxinfo com.gathin.tvhome reset')
    top = subprocess.Popen(base + ['shell', 'top -b -n 5 -d 1 -p ' + pid],
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    for _ in range(3):
        for key in [22, 22, 22, 21, 21, 21]:
            shell('input keyevent ' + str(key))
            time.sleep(0.12)
    result['cpu_navigation'], _ = top.communicate(timeout=20)
    time.sleep(.5)
    result['graphics'] = shell('dumpsys gfxinfo com.gathin.tvhome')
    result['memory_after_navigation'] = shell('dumpsys meminfo com.gathin.tvhome')
    target = state / ('performance-' + args.label + '.json')
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    target.chmod(0o600)
    for name in ['memory_idle', 'memory_after_navigation']:
        print(name, '\n'.join(l.strip() for l in result[name].splitlines() if 'TOTAL PSS:' in l))
    for name in ['cpu_idle', 'cpu_navigation']:
        print(name, '\n'.join(l.strip() for l in result[name].splitlines() if 'com.gathin.tvhome' in l))
    print('\n'.join(l for l in result['graphics'].splitlines() if any(k in l for k in
          ['Total frames', 'Janky frames', 'percentile', 'Number Missed Vsync'])))
    print('PERFORMANCE_SAMPLE_SAVED', args.label)


if __name__ == '__main__':
    main()
