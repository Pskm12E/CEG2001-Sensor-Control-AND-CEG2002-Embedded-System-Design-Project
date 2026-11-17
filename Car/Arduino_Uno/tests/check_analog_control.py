from pathlib import Path
import subprocess

root=Path(__file__).resolve().parents[1]
build=root/'build/analog_tests'
build.mkdir(parents=True,exist_ok=True)
exe=build/'analog_tests.exe'
subprocess.run(['C:/msys64/ucrt64/bin/g++.exe','-std=c++11','-Wall','-Wextra',
                '-Wno-unused-function','-Werror','-static',str(root/'tests/test_analog_control.cpp'),'-o',str(exe)],check=True)
subprocess.run([str(exe)],check=True)
