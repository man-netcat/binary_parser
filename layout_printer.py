from PyQt5.QtGui import QTextCharFormat, QTextCursor, QColor
from PyQt5.QtWidgets import QTextEdit, QVBoxLayout, QWidget
import sys
import random


class LayoutPrinter(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()
        self.previous_color = (0, 0, 0)
        self.color = (0, 0, 0)

    def random_color(self):
        while self.color == self.previous_color:
            r = random.randint(64, 192)
            g = random.randint(64, 192)
            b = random.randint(64, 192)
            self.color = (r, g, b)

    def initUI(self):
        self.textEdit = QTextEdit(self)
        self.textEdit.setReadOnly(True)

        vbox = QVBoxLayout()
        vbox.addWidget(self.textEdit)
        self.setLayout(vbox)

        self.setWindowTitle('Text Window')
        self.setGeometry(100, 100, 400, 300)
        self.show()

    def write_text(self, text, color=True):
        text = " ".join([text[i:i+2] for i in range(0, len(text), 2)])
        self.random_color()
        cursor = self.textEdit.textCursor()
        format = QTextCharFormat()
        if color:
            format.setForeground(QColor(*self.color))
        else:
            format.setForeground(QColor(0, 0, 0))
        format.setFontFamily('Courier')
        cursor.movePosition(QTextCursor.End)
        cursor.insertText(text, format)
        self.textEdit.setTextCursor(cursor)
        self.textEdit.ensureCursorVisible()
        self.previous_color = self.color
