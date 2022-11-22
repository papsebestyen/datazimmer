import os
import stat
from contextlib import contextmanager
from inspect import getmodule, stack
from itertools import chain
from pathlib import Path
from shutil import rmtree
from subprocess import check_call, check_output
from typing import Type, Union

from colassigner.util import camel_to_snake  # noqa: F401
from sqlalchemy.dialects.postgresql import dialect as postgres_dialect
from structlog import get_logger

LINE_LEN = 119
PRIMITIVE_MODULES = ["builtins", "datetime"]
package_root = Path(__file__).parent.parent

logger = get_logger("util")


def get_creation_module_name():
    # stack[2] as 0: utils, 1: dz module, 2: src/metazimmer
    try:
        return getmodule(stack()[2][0]).__name__
    except AttributeError:  # pragma: no cover
        logger.warning("can't get module name, likely due to notebook call")
        return None


def git_run(*, add=(), msg=None, pull=False, push=False, wd=None, clone=()):
    for k, git_cmd in [
        (clone, ["clone", "--depth", "1", *clone]),
        (pull, ["pull"]),
        (add, ["add", *add]),
        (msg, ["commit", "-m", msg]),
        (push, ["push"]),
    ]:
        if k:
            check_call(["git", *git_cmd], cwd=wd)


def get_git_diffs(staged=False):
    comm = ["git", "diff", "--name-only"]
    if staged:
        comm.append("--cached")
    diffs = check_output(comm)
    return [*filter(None, diffs.decode("utf-8").strip().split("\n"))]


@contextmanager
def cd_into(dirpath: Union[str, Path]):
    wd = os.getcwd()
    os.chdir(dirpath)
    # sys.path.insert(0, str(dirpath))
    try:
        yield
    finally:
        os.chdir(wd)
        # sys.path.pop(0)


def gen_rmtree(path: Path):
    if Path(path).exists():
        try:
            rmtree(path, onerror=_onerror)
        except PermissionError:  # pragma: no cover
            pass  # stupid windows


def _onerror(func, path, exc_info):  # pragma: no cover
    if not os.access(path, os.W_OK):
        os.chmod(path, stat.S_IWUSR)
        func(path)
    else:
        raise  # still stupid windows


def chainmap(fun, iterable) -> list:
    return [*chain(*map(fun, iterable))]


def is_postgres(engine):
    return isinstance(engine.dialect, postgres_dialect)


def get_simplified_mro(cls: Type):
    return _simplify_mro(cls.mro()[1:])


def _simplify_mro(parent_list: list[Type]):
    out = []
    for cls in parent_list:
        if any(map(lambda added_cls: cls in added_cls.mro(), out)):
            continue
        out.append(cls)
    return out
