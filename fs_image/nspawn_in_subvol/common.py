#!/usr/bin/env python3
# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

'No externally useful functions here.  Read the `run.py` docblock instead.'
import subprocess

from typing import Any, Callable

# This determines which binaries we shadow.  Our runtimes are expected to
# ensure that this is the PATH for the user command in the container.
#
# For now, the non-booted case implicitly uses the `systemd-nspawn` default
# `PATH`, so if that changes our test will fail.  That test failure in time
# will be an opportunity to decide whether to set our own, or follow.
DEFAULT_PATH = [
    '/usr/local/sbin',
    '/usr/local/bin',
    '/usr/sbin',
    '/usr/bin',
    '/sbin',
    '/bin',
]

_PopenCtxMgr = Any  # Quacks like `popen_{non_,}booted_nspawn`
# The intention of this wrapper API is to allow users of `run_*_nspawn` to
# wrap the underlying `popen_*_nspawn` implementation uniformly, without
# having to distinguish between the booted and non-booted cases.
_PopenWrapper = Callable[[_PopenCtxMgr], _PopenCtxMgr]


def _nspawn_version():
    '''
    We now care about the version of nspawn we are running.  The output of
    systemd-nspawn --version looks like:

    ```
    systemd 242 (v242-2.fb1)
    +PAM +AUDIT +SELINUX +IMA ...
    ```
    So we can get the major version as the second token of the first line.
    We hope that the output of systemd-nspawn --version is stable enough
    to keep parsing it like this.
    '''
    return int(subprocess.check_output([
        'systemd-nspawn', '--version']).split()[1])
