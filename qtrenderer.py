import os
import sys
import threading
from multiprocessing import Process
from PyQt5.QtCore import QTimer, Qt, QSize, QUrl, QCoreApplication, QEvent
from PyQt5.QtGui import QPixmap, QImage, QPainter, QRegion, QPaintEvent
from PyQt5.QtWidgets import QApplication
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEngineSettings

os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--enable-logging --log-level=3"


# https://github.com/spyder-ide/spyder-kernels/commit/62a3c6cad5149fd35e29795a7d46f73c536cb3be
class SpyderQApplication(QApplication):
    def __init__(self, *args, **kwargs):
        super(SpyderQApplication, self).__init__(*args, **kwargs)
        # Add reference to avoid destruction
        # This creates a Memory leak but avoids a Segmentation fault
        SpyderQApplication._instance_list.append(self)


SpyderQApplication._instance_list = []
QApplication = SpyderQApplication


# https://stackoverflow.com/questions/65769575/convert-html-to-png-with-width-dependent-on-content-locally
class QtRenderHtml(QWebEngineView):
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.loading = False
        # self.app.aboutToQuit.connect(self.app.deleteLater)
        super().__init__()  # self is QWebEngineView
        self.readytorender = False
        self.filename = "default.png"
        self.page().loadFinished.connect(self.finished)
        self.setAttribute(Qt.WA_DontShowOnScreen)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.installEventFilter(self)
        self.page().setBackgroundColor(Qt.transparent)
        self.page().settings().setAttribute(QWebEngineSettings.ShowScrollBars, False)
        settings = QWebEngineSettings.globalSettings()
        for attr in (QWebEngineSettings.PluginsEnabled,
                     QWebEngineSettings.ScreenCaptureEnabled,):
            settings.setAttribute(attr, True)

    def eventFilter(self, object, event):
        print(f"Event {event} {event.type()}")
        return True

    def resizeEvent(self, event):
        QWebEngineView.resizeEvent(self, event)

    def finished(self, ok):
        print(ok)
        # the function is to make sure bottom margins are included
        print(self.size().width())
        if self.size().width() > 20:
            self.screencap()
        func = """function outerHeight(element) {
                    const height = element.offsetHeight,
                        style = window.getComputedStyle(element)
                
                    return ['top', 'bottom']
                        .map(side => parseInt(style[`margin-${side}`]))
                        .reduce((total, side) => total + side, height)
                }"""
        self.page().runJavaScript(f"{func};document.documentElement.scrollWidth.toString()+"
                                  "\"x\"+"
                                  "outerHeight(document.body).toString();",
                                  self.getsizes)

    def getsizes(self, sizes):

        size = sizes.split("x")
        self.resize(QSize(int(size[0]), int(size[1])))
        self.page().runJavaScript("document.documentElement.scrollWidth.toString()+"
                                  "\"x\"+"
                                  "outerHeight(document.body).toString();",
                                  self.getsizes2)

    def getsizes2(self, sizes):
        size = sizes.split("x")
        self.resize(QSize(int(size[0]), int(size[1])))
        QTimer.singleShot(2000, self.screencap)
        print(size)
        # self.reload()
        # self.waitforrender(False)
        # self.page().runJavaScript("ready = false;", self.waitforrender)

    def waitforrender(self, arg):
        # self.reload()
        self.screencap()
        # if arg:
        #     self.screencap()
        # else:
        #     self.page().runJavaScript(
        #         "void(setTimeout(function(){ready=true;},1000))"
        #         "|| typeof ready !== 'undefined' && ready;",
        #         self.waitforrender)

    def screencap(self):
        pixmap = QImage(self.size(), QImage.Format_ARGB32)
        pixmap.fill(Qt.transparent)
        p = QPainter(pixmap)
        self.render(p)
        p.end()
        pixmap.save(self.filename, "PNG")
        self.app.exit()

    def startrender(self, html, filename):
        self.readytorender = False
        self.filename = filename
        self.resize(QSize(10, 10))  # ensure minimum possible size
        base = os.getcwd()
        if not base.endswith("/"):
            base += "/"
        self.setHtml(html, QUrl.fromLocalFile(base))
        self.show()

        # sys.exit(self.app.exec_())
        # self.loading = True
        # while self.loading:
        #     while self.app.hasPendingEvents():
        #         self.app.processEvents()
        self.app.exec_()

    # def rendermany(self, htmls):
    #     for html, outname in htmls.items():
    #         self.startrender(html, outname)


def html2png(html, outname):
    q = QtRenderHtml()
    q.startrender(html, outname)
    return outname


def processhtml2png(*args):
    html2png(*args)


# def htmls2png(inputdict: dict):
#     q = QtRenderHtml()
#     q.rendermany(inputdict)


def test():
    html2png("<p>image0</p>", "html.png")

# test()
