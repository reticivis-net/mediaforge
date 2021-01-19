import os
import sys

from PyQt5.QtCore import QTimer, Qt, QSize, QUrl
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import QApplication
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEngineSettings

os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--enable-logging --log-level=3"


class QtRenderHtml(QWebEngineView):
    def __init__(self):
        self.app = QApplication(sys.argv)
        super().__init__()  # self is QWebEngineView
        self.readytorender = False
        self.filename = "default.png"
        self.loadFinished.connect(self.finished)
        self.setAttribute(Qt.WA_DontShowOnScreen)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.page().setBackgroundColor(Qt.transparent)
        self.page().settings().setAttribute(QWebEngineSettings.ShowScrollBars, False)

    def resizeEvent(self, event):
        QWebEngineView.resizeEvent(self, event)

    def finished(self, ok):
        self.page().runJavaScript("document.documentElement.scrollWidth.toString()+"
                                  "\"x\"+"
                                  "document.documentElement.scrollHeight.toString();",
                                  self.getsizes)

    def getsizes(self, sizes):
        size = sizes.split("x")
        self.resize(QSize(int(size[0]), int(size[1])))
        self.page().runJavaScript("document.documentElement.scrollWidth.toString()+"
                                  "\"x\"+"
                                  "document.documentElement.scrollHeight.toString();",
                                  self.getsizes2)

    def getsizes2(self, sizes):
        size = sizes.split("x")
        self.resize(QSize(int(size[0]), int(size[1])))
        self.readytorender = False
        QTimer.singleShot(200, self.screencap)
        # print(size.width(), size.height())

    def screencap(self):
        pixmap = QPixmap(self.size())
        pixmap.fill(Qt.transparent)
        self.render(pixmap)
        pixmap.save(self.filename, "PNG")
        self.app.exit()

    def startrender(self, html, filename):
        self.readytorender = False
        self.filename = filename
        self.resize(QSize(0, 0))  # ensure minimum possible size
        base = os.getcwd()
        if not base.endswith("/"):
            base += "/"
        self.setHtml(html, QUrl.fromLocalFile(base))
        self.show()
        self.app.exec_()

    def rendermany(self, htmls):
        for html, outname in htmls.items():
            self.startrender(html, outname)


def html2png(html, outname):
    q = QtRenderHtml()
    q.startrender(html, outname)
    return outname


def htmls2png(inputdict: dict):
    q = QtRenderHtml()
    q.rendermany(inputdict)


def test():
    html2png("<p>image0</p>", "html.png")
    htmls2png({
        "<p>image1</p>": "htmls1.png",
        "<p>image2</p>": "htmls2.png",
        "<p>image3</p>": "htmls3.png",
        "<p>image4</p>": "htmls4.png",
    })

# test()
