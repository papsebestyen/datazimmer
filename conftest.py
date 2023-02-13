import os
import sys
from pathlib import Path
from subprocess import check_call
from tempfile import TemporaryDirectory

import boto3
import moto
import pytest
from aswan.constants import DEFAULT_REMOTE_ENV_VAR, DEPOT_ROOT_ENV_VAR
from aswan.depot.remote import HEX_ENV, PW_ENV
from dvc.config import Config as DvcConfig
from zimmauth import ZimmAuth
from zimmauth.core import LOCAL_HOST_NAMES_ENV_VAR

from datazimmer.config_loading import RunConfig
from datazimmer.naming import (
    AUTH_HEX_ENV_VAR,
    AUTH_PASS_ENV_VAR,
    DEFAULT_ENV_NAME,
    MAIN_MODULE_NAME,
)
from datazimmer.tests.create_dogshow import dogshow_root
from datazimmer.tests.util import dz_ctx
from datazimmer.typer_commands import cleanup, init, init_explorer
from datazimmer.utils import cd_into, gen_rmtree

CORE_PY = dogshow_root / "minimal.py"


def pytest_addoption(parser):
    # test / explore / live
    parser.addoption("--mode", action="store", default="test")


@pytest.fixture(scope="session")
def empty_template():
    _tmp = TemporaryDirectory()
    tmp_dir = Path(_tmp.name)
    dvc_rem = tmp_dir / "dvc-rem"
    pname = "test-project"
    with cd_into(tmp_dir):
        check_call(["git", "init", "remote"])
        init(pname, git_remote=(tmp_dir / "remote").as_posix())
    pdir = tmp_dir / pname
    with cd_into(pdir):
        check_call(["dvc", "remote", "add", "testrem", dvc_rem.as_posix()])
        check_call(["dvc", "remote", "default", "testrem"])
        Path(MAIN_MODULE_NAME, "core.py").write_text(CORE_PY.read_text())
    with dz_ctx([pdir]):
        yield pdir
    gen_rmtree(tmp_dir)


@pytest.fixture
def in_template(empty_template: Path):
    with cd_into(empty_template):
        sys.path.insert(0, empty_template.as_posix())
        yield empty_template
        sys.path.pop(0)


@pytest.fixture(scope="session")
def small_explorer():
    pass


@pytest.fixture
def running_template(in_template):
    _env = DEFAULT_ENV_NAME
    with RunConfig(write_env=_env, read_env=_env, profile=True):
        yield


@pytest.fixture(scope="session")
def test_bucket():

    with moto.mock_s3():
        conn = boto3.resource("s3")
        conn.create_bucket(Bucket="bucket-1")
        conn.create_bucket(Bucket="bucket-2")
        conn.create_bucket(Bucket="bucket-3")
        yield conn


@pytest.fixture
def proper_env():

    conf = DvcConfig()
    gpath = Path(conf.files.get("global"))

    old_conf = None
    if gpath.name and gpath.exists():
        old_conf = gpath.read_text()

    tmp_dir = TemporaryDirectory()
    tmp_path = Path(tmp_dir.name)
    rem_path, local_path = tmp_path / "aswan-remote", tmp_path / "aswan-local"
    rem_path.mkdir()
    local_path.mkdir()

    _CONN_NAME = "aswan-conn"
    _HOST = "localhost"
    my_pw = "ldb-siu"
    dic = {
        "keys": {
            "s3-key-name-1": {"key": "XYZ", "secret": "XXX"},
            "s3-key-name-2": {"key": "AB", "secret": "X", "endpoint": "http://sg.co"},
        },
        "bucket-1": {"key": "s3-key-name-1"},
        "bucket-2": {"key": "s3-key-name-2"},
        "bucket-3": {"key": "s3-key-name-1"},
        "rsa-keys": {"rand-key": "XYZ"},
        "ssh": {"ssh-name-1": {"host": _HOST, "user": "suzer", "rsa_key": "rand-key"}},
        _CONN_NAME: {"connection": "ssh-name-1", "path": rem_path.as_posix()},
    }
    my_hex = ZimmAuth.dumps_dict(dic, my_pw)

    os.environ[AUTH_HEX_ENV_VAR] = my_hex
    os.environ[AUTH_PASS_ENV_VAR] = my_pw
    os.environ[HEX_ENV] = my_hex
    os.environ[PW_ENV] = my_pw
    os.environ[LOCAL_HOST_NAMES_ENV_VAR] = _HOST
    os.environ[DEFAULT_REMOTE_ENV_VAR] = _CONN_NAME
    os.environ[DEPOT_ROOT_ENV_VAR] = local_path.as_posix()
    yield
    tmp_dir.cleanup()
    if old_conf:
        gpath.write_text(old_conf)
