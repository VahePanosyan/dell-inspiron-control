# Third-party components

The application code is MIT licensed. Bundled dependencies retain their own licenses.

* **Python 3.12** — Python Software Foundation license; copied into `licenses/python`.
  Sources: <https://www.python.org/downloads/source/>.
* **Qt / PySide6 / Shiboken 6.12.0** — used under the LGPL v3 option. Unmodified libraries are
  dynamically linked and remain separate files in `_internal`. Users may replace these libraries
  with ABI-compatible modified builds and may reverse engineer the combined work to debug such
  modifications as permitted by the LGPL. LGPL/GPL texts are in `licenses/`.
  Corresponding source and build instructions:
  <https://code.qt.io/pyside/pyside-setup.git/tree/?h=v6.12.0>,
  <https://code.qt.io/qt/qtbase.git/tree/?h=v6.12.0>,
  <https://doc.qt.io/qtforpython-6/building_from_source/index.html>.
  Qt module/third-party notices: <https://doc.qt.io/qtforpython-6/licenses.html> and
  <https://doc.qt.io/qt-6/licenses-used-in-qt.html>.
* **pywin32** — PSF-based/BSD-style component notices are copied from the installed distribution
  into `licenses/pywin32`. Sources: <https://github.com/mhammond/pywin32>.
* **nvidia-ml-py / pynvml** — NVIDIA BSD license, copied from the binding's source header into
  `licenses/nvidia-ml-py`. Sources: <https://pypi.org/project/nvidia-ml-py/>.
  The NVIDIA display driver and NVML runtime are not distributed by this application.
* **PyInstaller bootloader** — GPL with the bootloader exception allowing bundled applications
  under their own licenses. A copy of the license/exception is included under `licenses/PyInstaller`.
  Sources: <https://github.com/pyinstaller/pyinstaller>.
* Microsoft runtime DLLs included by Python/Qt retain Microsoft copyright and redistribution terms.
  System Windows ICU is used from the target OS; unrelated ICU binaries are excluded from this bundle.

The build records exact installed dependency versions in `build-versions.json` in the portable folder.
