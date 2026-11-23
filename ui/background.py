"""Run a blocking operation behind a modal Qt progress dialog."""

import csv

from PySide6 import QtCore, QtWidgets


class _Worker(QtCore.QRunnable):
    class Signals(QtCore.QObject):
        complete = QtCore.Signal(object)
        failed = QtCore.Signal(str)
        progress = QtCore.Signal(int, int, str)

    def __init__(self, work):
        super().__init__()
        self.work = work
        self.signals = self.Signals()

    @QtCore.Slot()
    def run(self):
        try:
            result = self.work(self.signals.progress.emit)
        except Exception as exc:
            self.signals.failed.emit(str(exc))
        else:
            self.signals.complete.emit(result)


def background(window, title, work, *, status="Working..."):
    dialog = QtWidgets.QProgressDialog(status, "", 0, 0, window)
    dialog.setWindowTitle(title)
    dialog.setCancelButton(None)
    dialog.setAutoClose(False)
    dialog.setAutoReset(False)
    dialog.setWindowModality(QtCore.Qt.WindowModality.ApplicationModal)
    dialog.setWindowFlag(QtCore.Qt.WindowType.WindowCloseButtonHint, False)
    loop = QtCore.QEventLoop()
    result, errors = [], []
    worker = _Worker(work)

    def progress(done, total, message):
        dialog.setLabelText(message)
        dialog.setMaximum(total)
        dialog.setValue(done)

    worker.signals.progress.connect(progress)
    worker.signals.complete.connect(result.append)
    worker.signals.failed.connect(errors.append)
    worker.signals.complete.connect(loop.quit)
    worker.signals.failed.connect(loop.quit)
    dialog.show()
    try:
        pool = getattr(window, "threadpool", QtCore.QThreadPool.globalInstance())
        pool.start(worker)
        loop.exec()
    finally:
        dialog.close()
        dialog.deleteLater()
    if errors:
        raise ValueError(errors[0])
    return result[0]
