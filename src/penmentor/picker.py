"""Windows stand-ins for rofi, slop and notify-send, each a small Qt window in its own process (desktop_win runs them):

  python -m penmentor.picker menu PROMPT      rows on stdin; prints the picked (or typed) row, exit 1 on Esc
                                              (--warm after PROMPT: no rows means "never mind", not a text box)
  python -m penmentor.picker region           drag a box; prints "x y w h" in desktop pixels, exit 1 on Esc
  python -m penmentor.picker toast TITLE MSG MS CRITICAL

Their own process, so penmentor's threads may call them while its Qt loop is busy drawing the marks.
"""
import sys

from . import desktop_win as W

from PyQt6.QtCore import QPoint, QRect, Qt, QTimer  # noqa: E402  (after desktop_win: DPI awareness first)
from PyQt6.QtGui import QColor, QCursor, QFont, QGuiApplication, QPainter, QPen  # noqa: E402
from PyQt6.QtWidgets import QApplication, QLabel, QLineEdit, QListWidget, QVBoxLayout, QWidget  # noqa: E402

BG, FG, DIM, ACCENT = '#16161a', '#E6E6E6', '#7A7A86', '#00DCFF'


def font(px):
    f = QFont('Segoe UI')
    f.setPixelSize(px)
    return f


def under_cursor():
    """The screen the pointer (or pen) is on: menus open where you are working."""
    return QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()


class Menu(QWidget):
    """rofi -dmenu -i: type to filter (case-insensitive), arrows to move, Enter picks (or sends what you typed),
    Esc gives up. Mouse and pen work too: a tap on a row picks it."""

    def __init__(self, rows, prompt):
        super().__init__(None, Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.rows, self.answer = rows, None
        self.setStyleSheet(f"""
            QWidget {{ background: {BG}; color: {FG}; }}
            QLineEdit {{ border: none; border-bottom: 1px solid #33333c; padding: 10px 14px; }}
            QListWidget {{ border: none; outline: none; padding: 4px 0; }}
            QListWidget::item {{ padding: 8px 14px; }}
            QListWidget::item:selected {{ background: #2a2a33; color: white; border-left: 3px solid {ACCENT}; }}""")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        self.edit = QLineEdit()
        self.edit.setFont(font(20))
        self.edit.setPlaceholderText(prompt + ('…' if rows else ': type and press Enter'))
        self.list = QListWidget()
        self.list.setFont(font(19))
        self.list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list.addItems(rows)
        lay.addWidget(self.edit)
        if rows:
            lay.addWidget(self.list)
        self.edit.textChanged.connect(self.filter)
        self.edit.returnPressed.connect(self.pick)
        self.list.itemClicked.connect(lambda item: self.done(item.text()))
        self.list.setCurrentRow(0)
        self.edit.installEventFilter(self)
        s = under_cursor().geometry()
        w = min(760, int(s.width() * .5))
        h = 52 + (min(len(rows), 14) * 40 + 10 if rows else 0)
        self.setGeometry(s.x() + (s.width() - w) // 2, s.y() + int(s.height() * .18), w, h)

    def filter(self, text):
        t = text.lower()
        for i in range(self.list.count()):
            self.list.item(i).setHidden(t not in self.list.item(i).text().lower())
        visible = [i for i in range(self.list.count()) if not self.list.item(i).isHidden()]
        if visible:
            self.list.setCurrentRow(visible[0])

    def eventFilter(self, obj, e):
        if e.type() == e.Type.KeyPress:
            k = e.key()
            if k == Qt.Key.Key_Escape:
                QApplication.exit(1)
                return True
            if k in (Qt.Key.Key_Down, Qt.Key.Key_Up, Qt.Key.Key_Tab, Qt.Key.Key_Backtab) and self.rows:
                step = 1 if k in (Qt.Key.Key_Down, Qt.Key.Key_Tab) else -1
                visible = [i for i in range(self.list.count()) if not self.list.item(i).isHidden()]
                if visible:
                    cur = self.list.currentRow()
                    j = visible.index(cur) if cur in visible else -1
                    self.list.setCurrentRow(visible[(j + step) % len(visible)])
                return True
        return False

    def pick(self):
        item = self.list.currentItem() if self.rows else None
        typed = self.edit.text()
        self.done(item.text() if item and not item.isHidden() else typed)

    def done(self, text):
        sys.stdout.write(text)
        sys.stdout.flush()
        QApplication.exit(0)

    def changeEvent(self, e):  # clicking elsewhere gives up, as rofi does
        if e.type() == e.Type.ActivationChange and not self.isActiveWindow() and getattr(self, 'had_focus', False):
            QApplication.exit(1)
        elif self.isActiveWindow():
            self.had_focus = True
        super().changeEvent(e)


class Region(QWidget):
    """slop: drag a box over the whole desktop (a faint veil shows it is waiting); Esc or a right-click gives up."""

    def __init__(self):
        super().__init__(None, Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setCursor(Qt.CursorShape.CrossCursor)
        g = QRect()
        for s in QGuiApplication.screens():
            g = g.united(s.geometry())
        self.setGeometry(g)
        self.a = self.b = None

    def paintEvent(self, e):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(0, 0, 0, 40))  # not fully transparent, or the clicks fall through
        if self.a and self.b:
            r = QRect(self.a, self.b).normalized()
            p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
            p.fillRect(r, Qt.GlobalColor.transparent)
            p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
            p.fillRect(r, QColor(0, 220, 255, 12))
            p.setPen(QPen(QColor(0, 220, 255, 230), 3))
            p.drawRect(r)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.RightButton:
            QApplication.exit(1)
        self.a = self.b = e.position().toPoint()
        self.update()

    def mouseMoveEvent(self, e):
        if self.a:
            self.b = e.position().toPoint()
            self.update()

    def mouseReleaseEvent(self, e):
        if not self.a:
            return
        r = QRect(self.a, e.position().toPoint()).normalized()
        if r.width() < 6 or r.height() < 6:  # a tap is not a box
            self.a = self.b = None
            return self.update()
        top = self.mapToGlobal(QPoint(0, 0))
        sys.stdout.write(f'{r.x() + top.x()} {r.y() + top.y()} {r.width()} {r.height()}')
        sys.stdout.flush()
        QApplication.exit(0)

    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_Escape:
            QApplication.exit(1)


class Toast(QLabel):
    """notify-send: bottom right of the screen under the pointer, gone after ms or on a click."""

    def __init__(self, title, msg, ms, critical):
        super().__init__(None, Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint |
                         Qt.WindowType.Tool | Qt.WindowType.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setTextFormat(Qt.TextFormat.PlainText)
        self.setText(f'{title}\n{msg}')
        self.setWordWrap(True)
        self.setFont(font(16))
        self.setStyleSheet(f'background: {"#9b1c1c" if critical else BG}; color: white; padding: 14px 18px;'
                           f'border-left: 4px solid {"white" if critical else ACCENT};')
        s = under_cursor().availableGeometry()
        self.setFixedWidth(min(460, s.width() - 40))
        self.adjustSize()
        self.move(s.right() - self.width() - 20, s.bottom() - self.height() - 20)
        QTimer.singleShot(ms, QApplication.quit)

    def mousePressEvent(self, e):
        QApplication.quit()


def main(a):
    app = QApplication(sys.argv[:1])
    app.setQuitOnLastWindowClosed(True)
    if a[:1] == ['menu']:
        rows = [r for r in sys.stdin.read().split('\n') if r]  # --warm: started early, the rows come when penmentor is ready
        if '--warm' in a[2:] and not rows:  # penmentor went away without asking
            return 1
        w = Menu(rows, a[1] if len(a) > 1 else '')
    elif a[:1] == ['region']:
        w = Region()
    elif a[:1] == ['toast']:
        title, msg, ms, critical = (a[1:] + ['penmentor', '', '5000', '0'][len(a) - 1:])[:4]
        w = Toast(title, msg, int(ms), critical == '1')
        w.show()
        return app.exec()
    else:
        print(__doc__, file=sys.stderr)
        return 2
    w.show()
    w.raise_()
    W.force_foreground(int(w.winId()))
    w.activateWindow()
    if isinstance(w, Menu):
        w.edit.setFocus()
    else:
        w.setFocus()
    return app.exec()


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
