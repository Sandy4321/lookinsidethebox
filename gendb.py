#!/usr/bin/env python3

import argparse
import py_compile
import logging
import marshal
import os
import sys
import zipfile

import opcodemap
import unmarshaller
import unpacker

logger = logging.getLogger(__name__)


def generate_opcode_mapping_from_zipfile(opc_map, zf, pydir):
    total = 0
    mapped = 0
    for fn in zf.namelist():
        if fn[-3:] != "pyc":
            continue
        with zf.open(fn, "r") as f:

            data = f.read(16)
            ulc = unpacker.load_code_without_patching
            um = unmarshaller.Unmarshaller(f.read)
            um.dispatch[unmarshaller.TYPE_CODE] = (ulc, "TYPE_CODE")
            remapped_co = um.load()

            total += 1

            # bytecompile the .py file to a .pyc file
            pyfn = os.path.join(pydir, fn[:-1])
            optimize = 2  # level is -OO
            try:
                py_compile.compile(pyfn, cfile=None, dfile=None, doraise=True,
                                   optimize=optimize)
                logger.debug("succesfully compiled %s" % pyfn)
            except Exception:
                continue

            # load the resulting .pyc file and compare it to the dropbox one
            try:
                libfile = os.path.join(pydir, "%s.cpython-37.opt-2.pyc" %
                                       (fn[:-4]))
                libfile = os.path.join(os.path.dirname(libfile),
                                       "__pycache__",
                                       os.path.basename(libfile))
                with open(libfile, "rb") as f:
                    f.read(16)
                    data = f.read()
                    orig_co = marshal.loads(data)
                    logger.info("mapping %s to %s" % (remapped_co.co_filename,
                                libfile))
                    opc_map.map_co_objects(remapped_co, orig_co)

                mapped += 1
            except FileNotFoundError:
                continue
    logger.info("Total .pyc files processed: %d" % total)
    logger.info("Total .pyc files mapped to Python standard library: %d" %
                mapped)


if __name__ == "__main__":

    try:
        assert(sys.version_info.major == 3 and sys.version_info.minor == 7)
    except AssertionError:
        print("Only Python 3.7.x is supported to generate the opcode db")
        sys.exit(1)

    root = logging.getLogger()
    root.setLevel(logging.WARNING)
    logger.setLevel(logging.DEBUG)
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    root.addHandler(handler)

    parser = argparse.ArgumentParser()
    parser.add_argument("--python-dir", required=True)
    parser.add_argument("--dropbox-zip", required=True)
    parser.add_argument("--db")
    ns = parser.parse_args()

    if not ns.db:
        ns.db = "opcode.db"

    with opcodemap.OpcodeMapping(ns.db, True) as opc_map:
        with zipfile.PyZipFile(ns.dropbox_zip,
                               "r",
                               zipfile.ZIP_DEFLATED) as zf:

            pydir = os.path.join(ns.python_dir, "Lib")
            generate_opcode_mapping_from_zipfile(opc_map, zf, pydir)
