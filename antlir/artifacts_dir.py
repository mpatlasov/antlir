#!/usr/bin/env python3
# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"DANGER: The resulting PAR will not work if copied outside of buck-out."
import os
import shutil
import stat
import subprocess
import sys
import textwrap
from typing import Optional

from .fs_utils import Path, populate_temp_file_and_rename


def _maybe_make_symlink_to_scratch(
    symlink_path: str, target_in_scratch, path_in_repo: str
) -> str:
    """
    IMPORTANT: This must be safe against races with other concurrent copies
    of `artifacts_dir.py`.
    """
    scratch_bin = shutil.which("mkscratch")
    if scratch_bin is None:
        return symlink_path

    # If the decode ever fails, we should probably switch this entire
    # function to return `bytes`.
    target_path, _ = (
        subprocess.check_output(
            [scratch_bin, "path", "--subdir", target_in_scratch, path_in_repo]
        )
        .decode()
        .rsplit("\n", 1)
    )

    # Atomically ensure the desired symlink exists.
    try:
        os.symlink(target_path, symlink_path)
    except FileExistsError:
        pass

    # These two error conditions should never happen under normal usage, so
    # they are left as exceptions instead of auto-remediations.
    if not os.path.islink(symlink_path):
        raise RuntimeError(
            f"{symlink_path} is not a symlink. Clean up whatever is there "
            "and try again?"
        )
    real_target = os.path.realpath(symlink_path)
    if real_target != target_path:
        raise RuntimeError(
            f"{symlink_path} points at {real_target}, but should point "
            f"at {target_path}. Clean this up, and try again?"
        )

    return target_path


def find_buck_cell_root(path_in_repo: Optional[str] = None) -> str:
    """
    If the caller does not provide a path known to be in the repo, a reasonable
    default of sys.argv[0] will be used. This is reasonable as binaries/tests
    calling this library are also very likely to be in repo.

    This is intended to work:
     - under Buck's internal macro interpreter, and
     - using the system python from `facebookincubator/antlir`.

    This is functionally equivalent to `buck root`, but we opt to do it here as
    `buck root` takes >2s to execute (due to CLI startup time).
    """
    if path_in_repo is None:
        path_in_repo = sys.argv[0]
    repo_path = os.path.abspath(path_in_repo)
    while True:
        if os.path.realpath(repo_path) == "/":  # No infinite loop on //
            raise RuntimeError(
                f"Could not find .buckconfig in any ancestor of {path_in_repo}"
            )
        if os.path.exists(os.path.join(repo_path, ".buckconfig")):
            return repo_path
        repo_path = os.path.dirname(repo_path)
    # Not reached


def ensure_per_repo_artifacts_dir_exists(
    path_in_repo: Optional[str] = None,
) -> str:
    "See `find_buck_cell_root`'s docblock to understand `path_in_repo`"
    repo_path = find_buck_cell_root(path_in_repo)
    artifacts_dir = os.path.join(repo_path, "buck-image-out")

    # On Facebook infra, the repo might be hosted on an Eden filesystem,
    # which is not intended as a backing store for a large sparse loop
    # device filesystem.  So, we will put our artifacts in a blessed scratch
    # space instead.
    #
    # The location in the scratch directory is a hardcoded path because
    # this really must be a per-repo singleton.
    real_dir = _maybe_make_symlink_to_scratch(
        artifacts_dir, "buck-image-out", repo_path
    )

    try:
        os.mkdir(real_dir)
    except FileExistsError:
        pass  # May race with another mkdir from a concurrent artifacts_dir.py

    ensure_clean_sh_exists(Path(artifacts_dir))
    return artifacts_dir


def ensure_clean_sh_exists(artifacts_dir: Path) -> None:
    clean_sh_path = artifacts_dir / "clean.sh"
    with populate_temp_file_and_rename(
        clean_sh_path, overwrite=True, mode="w"
    ) as f:
        # We do not want to remove image_build.log because the potential
        # debugging value far exceeds the disk waste
        f.write(
            textwrap.dedent(
                """\
            #!/bin/bash
            set -ue -o pipefail
            buck clean
            sudo umount -l buck-image-out/volume || true
            rm -f buck-image-out/image.btrfs
            # Just try to remove empty checkout dirs if they exist
            # Leave any checkouts as they may still be mounted by Eden
            REPOS="buck-image-out/eden/repos"
            mkdir -p "$REPOS"
            find "$REPOS" -maxdepth 2 -depth -type d -print0 | xargs -0 rmdir 2>/dev/null || true
            if [ -d "$REPOS" ]; then
                echo "Eden checkouts remain in $REPOS and were not cleaned up"
            else
                rm -rf buck-image-out/eden
            fi
        """  # noqa: E501
            )
        )
    os.chmod(
        clean_sh_path,
        os.stat(clean_sh_path).st_mode
        | (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH),
    )


if __name__ == "__main__":
    print(ensure_per_repo_artifacts_dir_exists())
