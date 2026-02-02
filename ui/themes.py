"""Theme management for UserManager application.

Provides light and dark mode themes with appropriate color schemes
for the application UI.
"""

from PySide6 import QtGui, QtWidgets


class ThemeManager:
    """Manages application themes and provides color schemes."""
    
    # Theme identifiers
    LIGHT = "light"
    DARK = "dark"
    
    def __init__(self):
        self.current_theme = self.LIGHT
        
    def set_theme(self, theme_name: str, app: QtWidgets.QApplication):
        """Apply the specified theme to the application.
        
        Args:
            theme_name: Either 'light' or 'dark'
            app: The QApplication instance
        """
        self.current_theme = theme_name
        
        if theme_name == self.DARK:
            self._apply_dark_theme(app)
        else:
            self._apply_light_theme(app)
    
    def get_current_theme(self) -> str:
        """Return the current theme name."""
        return self.current_theme
    
    def _apply_light_theme(self, app: QtWidgets.QApplication):
        """Apply light theme to the application."""
        # Reset to default light palette
        app.setStyleSheet("")
        app.setPalette(app.style().standardPalette())
    
    def _apply_dark_theme(self, app: QtWidgets.QApplication):
        """Apply dark theme to the application."""
        # Create a dark palette
        dark_palette = QtGui.QPalette()
        
        # Define dark theme colors
        dark_color = QtGui.QColor(53, 53, 53)
        disabled_color = QtGui.QColor(127, 127, 127)
        
        dark_palette.setColor(QtGui.QPalette.Window, dark_color)
        dark_palette.setColor(QtGui.QPalette.WindowText, QtGui.QColor(255, 255, 255))
        dark_palette.setColor(QtGui.QPalette.Base, QtGui.QColor(35, 35, 35))
        dark_palette.setColor(QtGui.QPalette.AlternateBase, dark_color)
        dark_palette.setColor(QtGui.QPalette.ToolTipBase, QtGui.QColor(255, 255, 255))
        dark_palette.setColor(QtGui.QPalette.ToolTipText, QtGui.QColor(255, 255, 255))
        dark_palette.setColor(QtGui.QPalette.Text, QtGui.QColor(255, 255, 255))
        dark_palette.setColor(QtGui.QPalette.Button, dark_color)
        dark_palette.setColor(QtGui.QPalette.ButtonText, QtGui.QColor(255, 255, 255))
        dark_palette.setColor(QtGui.QPalette.BrightText, QtGui.QColor(255, 0, 0))
        dark_palette.setColor(QtGui.QPalette.Link, QtGui.QColor(42, 130, 218))
        dark_palette.setColor(QtGui.QPalette.Highlight, QtGui.QColor(42, 130, 218))
        dark_palette.setColor(QtGui.QPalette.HighlightedText, QtGui.QColor(35, 35, 35))
        
        # Disabled colors
        dark_palette.setColor(QtGui.QPalette.Disabled, QtGui.QPalette.WindowText, disabled_color)
        dark_palette.setColor(QtGui.QPalette.Disabled, QtGui.QPalette.Text, disabled_color)
        dark_palette.setColor(QtGui.QPalette.Disabled, QtGui.QPalette.ButtonText, disabled_color)
        dark_palette.setColor(QtGui.QPalette.Disabled, QtGui.QPalette.Highlight, QtGui.QColor(80, 80, 80))
        dark_palette.setColor(QtGui.QPalette.Disabled, QtGui.QPalette.HighlightedText, QtGui.QColor(127, 127, 127))
        
        app.setPalette(dark_palette)
        
        # Additional stylesheet for specific widgets
        stylesheet = """
            QToolTip {
                color: #ffffff;
                background-color: #2a2a2a;
                border: 1px solid #555555;
            }
            QMenuBar::item:selected {
                background-color: #555555;
            }
            QMenu::item:selected {
                background-color: #555555;
            }
            QPushButton:hover {
                background-color: #666666;
            }
            QPushButton:pressed {
                background-color: #444444;
            }
        """
        app.setStyleSheet(stylesheet)
    
    def get_delete_button_style(self) -> str:
        """Return the appropriate style for the delete button based on current theme."""
        if self.current_theme == self.DARK:
            # Darker red for dark mode with better contrast
            return "background-color: #8b0000; color: white; font-weight: bold;"
        else:
            # Original red for light mode
            return "background-color: #d9534f; color: white;"
