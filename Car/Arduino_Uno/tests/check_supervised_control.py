"""Compile and run assertions against actual portable controller/protocol code."""
from pathlib import Path
import subprocess
ROOT=Path(__file__).resolve().parents[3]
build=ROOT/'Car/Arduino_Uno'/'build'
build.mkdir(exist_ok=True)
compiler=Path('C:/msys64/ucrt64/bin/g++.exe')
exe=build/'supervised_control_tests.exe'
subprocess.run([str(compiler),'-std=c++11','-Wall','-Wextra','-Werror','-static',
               str(Path(__file__).with_name('test_supervised_control.cpp')),'-o',str(exe)],check=True)
subprocess.run([str(exe)],check=True)
