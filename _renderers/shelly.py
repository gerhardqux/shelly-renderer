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

:maintainer: Gerhard Muntingh <gerhard@qux.nl>
:maturity: new
:platform: all
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


def _cmd_pkg(tokens, sls=''):
    '''
    Generate package installation resources.

    Installation of packages can be performed using:

    .. code-block:

        yum install <package>...

    Currently only pkg.installed is supported.

    :rtype: dict
    '''
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
    '''
    Generate directory resources.

    Directories can be created using:

    .. code-block:

        mkdir [-m <mode>] <dir>...

    :rtype: dict
    '''
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
    '''
    Modify the owner of files or directories.

    The owner of files and directories can be set using:

    .. code-block:

        chown user.group <file/directory>...

    :rtype: dict
    '''
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
    '''
    Retrieve remote files using curl.

    Files can be run through a template using the pipe syntax.

    Example:

    .. code-block:

        curl salt://dir/file.j2 | jinja2 > /tmp/file

    Permissions and ownership can be set using extra commands:

    .. code-block:

        chmod 0644 /tmp/file
        chown user:group /tmp/file

    Shelly will merge these into a single resource based in the
    salt id (.file./tmp/file).

    :rtype: dict
    '''
    resources = {}
    file_mngd = []
    tokens = iter(tokens)
    try:
        while True:
            t = next(tokens)
            if t == '|':
                file_mngd.append({'template': next(tokens)})
            elif t == '>':
                file_name = next(tokens)
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
    '''
    Create users using useradd.

    Example:

    .. code-block:

        # create the user influxdb
        useradd -d /opt/influxdb -s /bin/bash -c InfluxDBServiceUser influxdb

    The usual useradd commands apply.

      * -d to specify the users home dir
      * -s to specify the users shell
      * -c to specify the comment or full name

    :rtype: dict
    '''
    resources = {}
    u = []
    tokens = iter(tokens)
    try:
        while True:
            t = next(tokens)
            if t == '-d':
                u.append({'home': next(tokens)})
            elif t == '-s':
                u.append({'shell': next(tokens)})
            elif t == '-c':
                u.append({'fullname': next(tokens)})
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
            t = next(tokens)
            if t == '-P':
                f.append({'chain': next(tokens)})
                f.append({'policy': next(tokens)})
                state = 'iptables.set_policy'
            elif t == '-I':
                f.append({'position': next(tokens)})
                state = 'iptables.insert'
            elif t == '-A':
                f.append({'chain': next(tokens)})
            elif t == '-s':
                f.append({'source': next(tokens)})
            elif t == '--connstate':
                f.append({'connstate': next(tokens)})
            elif t == '--dport':
                f.append({'dport': next(tokens)})
            elif t == '--proto':
                f.append({'proto': next(tokens)})
            elif t == '--match':
                f.append({'match': next(tokens).split(',')})
            elif t == '--comment':
                f.append({'save': True})
                sid = _generate_sid(sls, 'iptables', next(tokens))
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


def _generate_sid(sls, state_mod, id):
    '''
    Generate a predictable salt id for a resource.

    Shell scripts perform multiple actions to the same resource using
    multiple commands. Saltstack creates a single resource for these
    different commands. E.g.

    .. code-block:

        wget http://example.org/file.txt
        chown user:group file.txt
        chmod 0644 file.txt

    Becomes:

    .. code-block:

        .file.file.txt:
          file.managed
            - source: http://example.org/file.txt
            - user: user
            - group: group
            - mode: 0644

    The wget, chown, and chmod commands all generate the same salt id,
    and these will be merged (in the merge_resources function) into a
    single resource.

    :rtype: string
    '''
    if state_mod == 'mkdir':
        state_mod = 'file'
    if state_mod == 'yum':
        state_mod = 'pkg'
    return "{0}.{1}.{2}".format(sls, state_mod, id)


def merge_resources(src, dest):
    '''
    Merge a resource into an existing resources dict.

    The render function returns a big ordered dict with all the
    defined resources in it. This function adds a resource to
    that dict.

    .. code-block:

        src = {
            '.svc.postfix': {
                'service.enabled': [
                    {'name': 'postfix'},
                ]
            }
        }
        dest = {
            '.svc.dovecot': {
                'service.enabled': [
                    {'name': 'dovecot'},
                ]
            },
        }

    Becomes:

    .. code-block:

        dest = {
            '.svc.postfix': {
                'service.enabled': [
                    {'name': 'postfix'},
                ]
            },
            '.svc.dovecot': {
                'service.enabled': [
                    {'name': 'dovecot'},
                ]
            },
        }

    There are some special rules that ensure existing resources, which all
    have the same salt id, get merged into each other.

    As described in the _generate_sid function:

    The wget, chown, and chmod commands all generate the same salt id,
    and these will be merged into a single resource.

    :rtype: dict
    '''
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
        sys.stderr.write('Please specify one filename on the command line.')
        sys.exit(1)
    filename = sys.argv[1]
    data = open(filename, 'rt').read()
    yaml.dump(render(data), sys.stdout)

if __name__ == '__main__':
    main()
