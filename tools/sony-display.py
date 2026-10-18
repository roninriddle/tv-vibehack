#!/usr/bin/env python3
"""Save, test and restore the TV's Android UI size and density."""
import argparse
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parent.parent


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['backup', 'apply-4k', 'restore', 'status'])
    parser.add_argument('--serial')
    args = parser.parse_args()
    state = ROOT / '.local'
    serial = args.serial or json.loads((state / 'device.json').read_text())['serial']
    base = [str(state / 'tools/platform-tools/adb'), '-P', '15037']
    p = subprocess.run(base + ['connect', serial], capture_output=True, text=True, timeout=12)
    if 'connected to' not in p.stdout:
        raise RuntimeError('无法连接电视，请提供无线调试主页的当前 IP:端口。')

    def shell(cmd):
        p = subprocess.run(base + ['-s', serial, 'shell', cmd], capture_output=True,
                           text=True, timeout=20)
        if p.returncode or 'Exception' in p.stderr:
            raise RuntimeError(p.stderr or p.stdout)
        return p.stdout.strip()

    file = state / 'display-baseline.json'

    def restore():
        original = json.loads(file.read_text())
        shell('wm size ' + (original['size_override'] or 'reset'))
        shell('wm density ' + (original['density_override'] or 'reset'))
        return shell('wm size'), shell('wm density')

    if args.action == 'backup':
        if file.exists():
            print('原显示参数已保存，保留原始备份。')
            return
        size, density = shell('wm size'), shell('wm density')
        a, b = re.search(r'Override size:\s*(\d+x\d+)', size), re.search(r'Override density:\s*(\d+)', density)
        file.write_text(json.dumps({'size': size, 'density': density,
                                   'size_override': a.group(1) if a else None,
                                   'density_override': b.group(1) if b else None}, indent=2))
        file.chmod(0o600)
        print('原显示参数已保存。')
    elif args.action == 'status':
        print(shell('wm size'))
        print(shell('wm density'))
    elif args.action == 'restore':
        print('\n'.join(restore()))
        print('已恢复原显示参数。')
    else:
        if not file.exists():
            raise RuntimeError('请先保存原显示参数。')
        try:
            shell('wm size 3840x2160')
            shell('wm density 640')
            size, density = shell('wm size'), shell('wm density')
            actual_size = re.search(r'Override size:\s*(\d+x\d+)', size) or re.search(r'Physical size:\s*(\d+x\d+)', size)
            actual_density = re.search(r'Override density:\s*(\d+)', density) or re.search(r'Physical density:\s*(\d+)', density)
            if not actual_size or actual_size.group(1) != '3840x2160' or not actual_density or actual_density.group(1) != '640':
                raise RuntimeError('4K 显示参数未通过复读检查。')
            shell('am force-stop com.gathin.tvhome')
            shell('am start -W -n com.gathin.tvhome/.MainActivity')
            print(size + '\n' + density)
            print('4K 参数已应用；保留恢复脚本，继续进行画面和性能验证。')
        except Exception:
            restore()
            raise


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print('操作未完成：' + str(error))
        raise SystemExit(1)
