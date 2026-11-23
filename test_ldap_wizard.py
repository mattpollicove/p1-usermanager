import os
import threading
import unittest
from unittest.mock import patch

from PySide6 import QtCore, QtWidgets

from ui.dialogs import ImportWizardDialog, LDAPConnectionsManager
from ui.dialogs import test_ldap_connection_with_status as run_ldap_test


class LDAPWizardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def test_manager_selection_reaches_import_on_next(self):
        connections = {"First": {}, "Second": {}}
        parent = QtWidgets.QWidget()
        parent._read_config = lambda: {"ldap_connections": connections}

        def manage():
            manager = LDAPConnectionsManager(connections, parent, allow_selection=True)
            manager.list_widget.setCurrentRow(1)
            manager.use_btn.click()
            return manager.selected_connection

        wizard = ImportWizardDialog(parent, ldap_connections=connections,
                                    manage_ldap_callback=manage, last_method="ldap")
        accepted = []
        wizard.accepted.connect(lambda: accepted.append(wizard.get_result().copy()))
        wizard.next_btn.click()
        self.assertEqual(wizard.conn_combo.currentText(), "First")
        wizard._manage_ldap_connections()
        self.assertEqual(wizard.conn_combo.currentText(), "Second")
        wizard.next_btn.click()
        self.assertEqual(accepted, [{"source_type": "ldap", "connection_name": "Second"}])

    def test_manager_close_preserves_selection(self):
        connections = {"First": {}, "Second": {}}
        parent = QtWidgets.QWidget()
        parent._read_config = lambda: {"ldap_connections": connections}
        wizard = ImportWizardDialog(parent, ldap_connections=connections,
                                    manage_ldap_callback=lambda: None, last_method="ldap")
        wizard.next_btn.click()
        wizard.conn_combo.setCurrentText("Second")
        wizard._manage_ldap_connections()
        self.assertEqual(wizard.conn_combo.currentText(), "Second")

    def test_status_is_visible_while_ldap_test_runs(self):
        parent = QtWidgets.QWidget()
        release = threading.Event()
        visible = []
        ran_in_worker = []

        def test_connection(*_args, **_kwargs):
            ran_in_worker.append(QtCore.QThread.currentThread() != self.app.thread())
            release.wait(2)
            return False, "Base DN not found"

        def inspect_status():
            dialog = parent.findChild(QtWidgets.QProgressDialog)
            if dialog is not None and dialog.isVisible():
                visible.append(dialog.labelText())
            release.set()

        QtCore.QTimer.singleShot(0, inspect_status)
        with patch("api.ldap_utils.test_connection", side_effect=test_connection):
            result = run_ldap_test(parent, {})
        self.assertEqual(result, (False, "Base DN not found"))
        self.assertEqual(ran_in_worker, [True])
        self.assertEqual(visible, ["Testing the LDAP bind and Base DN..."])


if __name__ == "__main__":
    unittest.main()
