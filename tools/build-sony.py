#!/usr/bin/env python3
"""Build the Sony trial APK with official SDK tools and public Maven artifacts."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import urllib.request
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parent.parent
NS = {'m': 'http://maven.apache.org/POM/4.0.0'}
ANDROID = 'http://schemas.android.com/apk/res/android'
ET.register_namespace('android', ANDROID)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--java-home', required=True)
    parser.add_argument('--sdk', required=True)
    args = parser.parse_args()
    java = Path(args.java_home)
    sdk = Path(args.sdk)
    build = ROOT / '.local' / 'direct-build'
    cache = ROOT / '.local' / 'maven'
    build.mkdir(parents=True, exist_ok=True)
    cache.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env['JAVA_HOME'] = str(java)
    env['PATH'] = str(java / 'bin') + os.pathsep + env['PATH']
    tools = sdk / 'build-tools' / '34.0.0'
    android_jar = sdk / 'platforms' / 'android-34' / 'android.jar'

    def run(argv):
        subprocess.run([str(a) for a in argv], check=True, env=env)

    def fetch(group, artifact, version, suffix):
        path = '/'.join([group.replace('.', '/'), artifact, version,
                         artifact + '-' + version + '.' + suffix])
        dest = cache / path
        if not dest.exists():
            base = ('https://dl.google.com/dl/android/maven2/' if group.startswith('androidx.')
                    else 'https://repo.maven.apache.org/maven2/')
            dest.parent.mkdir(parents=True, exist_ok=True)
            with urllib.request.urlopen(base + path, timeout=45) as response:
                data = response.read()
            dest.write_bytes(data)
        return dest

    def version_key(v):
        return tuple(int(x) for x in re.findall(r'\d+', v))

    selected = {}
    pending = [('androidx.recyclerview', 'recyclerview', '1.3.2'),
               ('androidx.dynamicanimation', 'dynamicanimation', '1.0.0')]
    while pending:
        group, artifact, version = pending.pop(0)
        version = version.strip('[]')
        key = group, artifact
        if key in selected and version_key(selected[key][0]) >= version_key(version):
            continue
        pom = ET.parse(fetch(group, artifact, version, 'pom')).getroot()
        packaging = pom.findtext('m:packaging', 'jar', NS)
        selected[key] = version, packaging
        properties = {e.tag.split('}')[-1]: e.text for e in pom.findall('m:properties/*', NS)}
        for dep in pom.findall('m:dependencies/m:dependency', NS):
            scope = dep.findtext('m:scope', 'compile', NS)
            if scope not in ['compile', 'runtime'] or dep.findtext('m:optional', '', NS) == 'true':
                continue
            g = dep.findtext('m:groupId', '', NS)
            a = dep.findtext('m:artifactId', '', NS)
            v = dep.findtext('m:version', '', NS)
            for name, value in properties.items():
                v = v.replace('${' + name + '}', value or '')
            if not v or '${' in v or ',' in v:
                raise RuntimeError('Unsupported dependency version: ' + str((g, a, v)))
            pending.append((g, a, v))

    jars, resources, packages, lock = [], [], [], []
    for (group, artifact), (version, packaging) in sorted(selected.items()):
        if packaging == 'pom':
            continue
        file = fetch(group, artifact, version, packaging)
        lock.append({'module': group + ':' + artifact + ':' + version,
                     'sha256': hashlib.sha256(file.read_bytes()).hexdigest()})
        if packaging == 'jar':
            jars.append(file)
            continue
        if packaging != 'aar':
            raise RuntimeError('Unsupported artifact: ' + str(file))
        dest = build / 'libraries' / (group + '-' + artifact)
        dest.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(file) as z:
            for member in z.infolist():
                target = (dest / member.filename).resolve()
                if not target.is_relative_to(dest.resolve()):
                    raise RuntimeError('Invalid archive path')
                z.extract(member, dest)
        if (dest / 'classes.jar').exists():
            jars.append(dest / 'classes.jar')
        jars.extend((dest / 'libs').glob('*.jar'))
        package = ET.parse(dest / 'AndroidManifest.xml').getroot().get('package')
        if package:
            packages.append(package)
        if (dest / 'res').is_dir() and any((dest / 'res').rglob('*.*')):
            output = dest / 'resources.zip'
            run([tools / 'aapt2', 'compile', '--dir', dest / 'res', '-o', output])
            resources.append(output)
    (build / 'dependencies.json').write_text(json.dumps(lock, indent=2))
    print('DEPENDENCIES_READY', len(lock), flush=True)

    src = ROOT / 'launcher' / 'app' / 'src' / 'main'
    manifest = ET.parse(src / 'AndroidManifest.xml')
    top = manifest.getroot()
    top.set('package', 'com.gathin.tvhome')
    gradle = (ROOT / 'launcher/app/build.gradle').read_text()
    version_code = re.search(r'versionCode\s+(\d+)', gradle).group(1)
    version_name = re.search(r"versionName\s+'([^']+)'", gradle).group(1)
    target_sdk = re.search(r'targetSdk\s+(\d+)', gradle).group(1)
    top.set('{' + ANDROID + '}versionCode', version_code)
    top.set('{' + ANDROID + '}versionName', version_name)
    top.insert(0, ET.Element('uses-sdk', {'{' + ANDROID + '}minSdkVersion': '26',
                                         '{' + ANDROID + '}targetSdkVersion': target_sdk}))
    mf = build / 'AndroidManifest.xml'
    manifest.write(mf, encoding='utf-8', xml_declaration=True)
    app_res = build / 'app-resources.zip'
    run([tools / 'aapt2', 'compile', '--dir', src / 'res', '-o', app_res])
    gen = build / 'generated'
    if gen.exists():
        shutil.rmtree(gen)
    gen.mkdir()
    resource_apk = build / 'resources.apk'
    command = [tools / 'aapt2', 'link', '-o', resource_apk, '--manifest', mf,
               '-I', android_jar, '--java', gen, '--auto-add-overlay',
               '--extra-packages', ':'.join(packages)]
    for res in resources + [app_res]:
        command.extend(['-R', res])
    run(command)
    classes = build / 'classes'
    if classes.exists():
        shutil.rmtree(classes)
    classes.mkdir()
    sources = sorted((src / 'java').rglob('*.java')) + sorted(gen.rglob('*.java'))
    run([java / 'bin' / 'javac', '-encoding', 'UTF-8', '--release', '8',
         '-classpath', os.pathsep.join(map(str, [android_jar] + jars)),
         '-d', classes] + sources)
    app_jar = build / 'app-classes.jar'
    run([java / 'bin' / 'jar', 'cf', app_jar, '-C', classes, '.'])
    dex = build / 'dex'
    dex.mkdir(exist_ok=True)
    run([java / 'bin' / 'java', '-cp', tools / 'lib' / 'd8.jar',
         'com.android.tools.r8.D8', '--min-api', '26', '--lib', android_jar,
         '--output', dex, app_jar] + jars)
    unsigned = build / 'unsigned.apk'
    shutil.copyfile(resource_apk, unsigned)
    with zipfile.ZipFile(unsigned, 'a') as z:
        for file in dex.glob('classes*.dex'):
            z.write(file, file.name)
    aligned = build / 'aligned.apk'
    run([tools / 'zipalign', '-f', '4', unsigned, aligned])
    key = ROOT / '.local' / 'sony-debug.keystore'
    if not key.exists():
        run([java / 'bin' / 'keytool', '-genkeypair', '-keystore', key,
             '-storepass', 'android', '-keypass', 'android', '-alias', 'androiddebugkey',
             '-dname', 'CN=Android Debug,O=Local Development,C=US', '-keyalg', 'RSA',
             '-keysize', '2048', '-validity', '10000'])
        key.chmod(0o600)
    output = ROOT / 'outputs'
    output.mkdir(exist_ok=True)
    apk = output / 'sony-tvhome-trial.apk'
    run([tools / 'apksigner', 'sign', '--ks', key, '--ks-key-alias', 'androiddebugkey',
         '--ks-pass', 'pass:android', '--key-pass', 'pass:android', '--out', apk, aligned])
    run([tools / 'apksigner', 'verify', '--verbose', apk])
    print('APK_READY', apk, hashlib.sha256(apk.read_bytes()).hexdigest(), flush=True)


if __name__ == '__main__':
    main()
