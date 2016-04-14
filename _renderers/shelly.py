'''
Shelly renderer for Salt

Create salt states with a shell like syntax. States are commonly written in
yaml, which is easy, but places a limit on functionality and flexibility.
To gain more functionality and flexibility, you can template your yaml
using jinja2, at the cost of easyness. You can go one step further, and
obtain maximum functionality and flexibility by writing your states in python.
This is even more difficult.

Salt encourages simplicity and thus suggests you gravitate down to yaml as much
as possible.

Shelly embraces this gravity and trades even more functionality and
flexibility for ease and simplicity.

Having said that, shelly is no shell, and one soon hits its limits.
Instead of adding functionality to shelly, you are encouraged to move up
to yaml+jinja in all but the most basic situations.

Shelly expects imperative form (e.g. install this package) instead of
declarative form (e.g. this package should be installed). This is really
an illusion for the user who is accustomed to shell scripts. Every line
is translated to a declarative datastructure anyway.
'''

from __future__ import absolute_import

# Import salt libs
import logging
import shlex
import re
import sys
import yaml
import collections

from salt.ext.six import string_types
from salt.exceptions import SaltRenderError

log = logging.getLogger(__name__)


def _generate_sid(sls, state_mod, id):
    if state_mod == 'mkdir':
        state_mod = 'file'
    if state_mod == 'yum':
        state_mod = 'pkg'
    return "{0}.{1}.{2}".format(sls, state_mod, id)


def _cmd_pkg(tokens, sls=''):
    # grep everything that looks like a word
    packages = [p for p in tokens[1:] if re.search(r'^[a-zA-Z0-9]\w+$', p)]

    if len(packages) == 0:
        return (None, None)

    resources = {}
    for p in packages:
        sid = _generate_sid(sls, 'pkg', p)
        resources[sid] = {'pkg.installed': [
            {'name': p}
        ]}
    return resources


def _cmd_mkdir(tokens, sls=''):
    dirmode = None
    if tokens[0] == '-m':
        dirmode = {'mode': tokens[1]}
        tokens = tokens[2:]
        log.info(tokens)

    if len(tokens) == 0:
        raise SaltRenderError(
            'mkdir without arguments')

    resources = {}
    for t in tokens:
        sid = _generate_sid(sls, 'file', t)
        resources[sid] = {'file.directory': [
            {'name': t}
        ]}

        if dirmode:
            resources[sid]['file.directory'].append(dirmode)

    return resources


def _cmd_chown(tokens, sls=''):
    match = re.match(r'^(\w+)[:\.](\w+)$', tokens[0])
    if not match:
        raise SaltRenderError(
            'usage: chown $user:$group <files>')

    user = match.group(1)
    group = match.group(2)

    tokens = tokens[1:]

    if len(tokens) == 0:
        raise SaltRenderError(
            'chown without arguments')

    resources = {}
    for t in tokens:
        sid = _generate_sid(sls, 'file', t)
        resources[sid] = {'file.directory': [
            {'name': t},
            {'user': user},
            {'group': group},
        ]}
    return resources


def _cmd_curl(tokens, sls=''):
    resources = {}
    file_mngd = []
    tokens = iter(tokens)
    try:
        while True:
            t = tokens.next()
            if t == '|':
                file_mngd.append({'template': tokens.next()})
            elif t == '>':
                file_name = tokens.next()
                file_mngd.append({'name': file_name})
                sid = _generate_sid(sls, 'file', file_name)
            else:
                file_mngd.append({'source': t})
    except StopIteration:
        pass
    if sid:
        resources[sid] = {'file.managed': file_mngd}
    else:
        raise SaltRenderError(
            'Shelly requires a rather strict curl'
            ' command ending in "> <filename>"')
    return resources


def _cmd_useradd(tokens, sls=''):
    resources = {}
    u = []
    tokens = iter(tokens)
    try:
        while True:
            t = tokens.next()
            if t == '-d':
                u.append({'home': tokens.next()})
            elif t == '-s':
                u.append({'shell': tokens.next()})
            elif t == '-c':
                u.append({'fullname': tokens.next()})
            else:
                u.append({'name': t})
                sid = _generate_sid(sls, 'user', t)
    except StopIteration:
        pass
    if sid:
        resources[sid] = {'user.present': u}
    else:
        raise SaltRenderError(
            'Shelly requires a rather strict useradd'
            ' command')
    return resources


def _cmd_iptables(tokens, sls=''):
    state = 'iptables.append'
    sid = None
    f = []
    tokens = iter(tokens)
    try:
        while True:
            t = tokens.next()
            if t == '-P':
                f.append({'chain': tokens.next()})
                f.append({'policy': tokens.next()})
            elif t == '-I':
                f.append({'position': tokens.next()})
                state = 'iptables.insert'
            elif t == '-A':
                f.append({'chain': tokens.next()})
            elif t == '-s':
                f.append({'source': tokens.next()})
            elif t == '--connstate':
                f.append({'connstate': tokens.next()})
            elif t == '--dport':
                f.append({'dport': tokens.next()})
            elif t == '--proto':
                f.append({'proto': tokens.next()})
            elif t == '--match':
                f.append({'match': tokens.next().split(',')})
            elif t == '--comment':
                f.append({'save': True})
                sid = _generate_sid(sls, 'iptables', tokens.next())
    except StopIteration:
        if not sid:
            raise SaltRenderError(
                'Shelly requires a rather strict iptables command')
        return {sid: {state: f}}


def _cmd_systemctl(tokens, sls=''):
    if tokens[0] == 'start':
        state = 'service.running'
    elif tokens[0] == 'stop':
        state = 'service.dead'
    elif tokens[0] == 'enable':
        state = 'service.enabled'
    elif tokens[0] == 'disable':
        state = 'service.enabled'
    else:
        raise SaltRenderError(
            'Shelly requires a rather strict systemctl command')
    # grep everything that looks like a word
    services = [s for s in tokens[1:] if re.search(r'^[a-zA-Z0-9]\w+$', s)]
    if len(services) == 0:
        return (None, None)
    resources = {}
    for s in services:
        sid = _generate_sid(sls, 'svc', s)
        resources[sid] = {state: [
            {'name': s}
        ]}
    return resources


def _cmd_ldso(tokens, sls=''):
    cmd = ' '.join(tokens)
    return {
        cmd: 'cmd.run'
    }

# Dispatch Table
dtable = {
    "yum": _cmd_pkg,
    "apt-get": _cmd_pkg,
    "mkdir": _cmd_mkdir,
    "chown": _cmd_chown,
    "curl": _cmd_curl,
    "useradd": _cmd_useradd,
    "iptables": _cmd_iptables,
    "systemctl": _cmd_systemctl,
    "ld.so": _cmd_ldso,
}


def all_resources(state):
    result = list()

    for rname, mods in state:
        for modname, _ in mods:
            modn = modname.split('.')
            result.append({modn[0]: rname})


def merge_resources(src, dest):
    for key, value in src.items():
        # No match, easy merge
        if key not in dest:
            dest[key] = value
            continue
        # collision,
        for srcmod, srcvalues in src[key].items():
            if srcmod in dest[key]:
                destmod = srcmod
            elif srcmod == 'file.directory' and \
                    'file.managed' in dest[key]:
                destmod = 'file.managed'
            else:
                # No match, easy merge
                dest[key][srcmod] = src[key][srcmod]
                continue
            destvalues = dest[key][destmod]
            for h in srcvalues:
                if 'name' not in h:
                    destvalues.append(h)
    return dest


def render(data, saltenv='base', sls='', **kws):
    '''
    Accepts shelly script as a string or as a file object and translates
    common shell instructions to salt states.

    :rtype: A Python data structure
    '''
    result = collections.OrderedDict()

    if not isinstance(data, string_types):
        data = data.read()

    if data.startswith('#!'):
        data = data[(data.find('\n') + 1):]
    if not data.strip():
        return {}

    lineno = 0
    for line in data.split('\n'):
        lineno += 1

        tokens = shlex.split(line, comments=True)
        if len(tokens):
            cmd = tokens[0]
            match = re.match(r'^/(.+)$', line)
            if match:
                cmd = 'ld.so'
                tokens = [cmd] + tokens
            if cmd in dtable:
                new_resources = dtable[cmd](tokens[1:], sls)
                merge_resources(new_resources, result)

    log.info(result)
    return result


def main():
    if len(sys.argv) != 2:
        print 'Please specify one filename on the command line.'
        sys.exit(1)
    filename = sys.argv[1]
    data = file(filename, 'rt').read()
    yaml.dump(render(data), sys.stdout)

if __name__ == '__main__':
    main()
