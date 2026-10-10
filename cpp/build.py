import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCE = os.path.join(HERE, "indicators.cpp")
OUTPUT_NAME = {"win32": "indicators.dll", "darwin": "libindicators.dylib"}.get(sys.platform, "libindicators.so")
OUTPUT = os.path.join(HERE, OUTPUT_NAME)

WINDOWS_GPP_PATHS = [
    r"C:\msys64\ucrt64\bin\g++.exe",
    r"C:\msys64\mingw64\bin\g++.exe",
]


def find_compiler():
    for name in ("g++", "clang++"):
        found = shutil.which(name)
        if found:
            return found
    if sys.platform == "win32":
        for path in WINDOWS_GPP_PATHS:
            if os.path.exists(path):
                return path
    return None


def main():
    compiler = find_compiler()
    if not compiler:
        print("No C++ compiler found.\n")
        if sys.platform == "win32":
            print("Windows: install MSYS2 (msys2.org), open the 'MSYS2 UCRT64' terminal and run:")
            print("    pacman -S mingw-w64-ucrt-x86_64-gcc")
            print("Then run this script again.")
        elif sys.platform == "darwin":
            print("macOS: run  xcode-select --install  and try again.")
        else:
            print("Linux: install g++ (for example  sudo apt install g++ ) and try again.")
        print("\nThe project still works without it, using the pandas versions.")
        return 1

    cmd = [compiler, "-O3", "-shared", "-o", OUTPUT, SOURCE]
    if sys.platform == "win32":
        cmd += ["-static"]  # link everything in, so Python finds no missing DLLs at runtime
    elif sys.platform != "darwin":
        cmd.insert(1, "-fPIC")

    print("Running:", " ".join(cmd))
    result = subprocess.run(cmd)
    if result.returncode != 0:
        print("\nBuild failed. Check the compiler messages above.")
        return result.returncode

    print(f"\nBuilt {OUTPUT}")
    print("Check it with:  python cpp/benchmark.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())