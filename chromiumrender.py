import io
import json
import logging
import os
import subprocess
import sys
import time
import typing
import zipfile
from concurrent.futures.process import BrokenProcessPool
from io import SEEK_END, SEEK_SET, BytesIO

import psutil
import requests
import selenium.common
from selenium import webdriver

import config
from clogs import logger
from tempfiles import temp_file


class ResponseStream(typing.IO):
    """
    stream a requests response as a file-like object.
    https://gist.github.com/obskyr/b9d4b4223e7eaf4eedcd9defabb34f13
    """

    def __init__(self, request_iterator):
        self._bytes = BytesIO()
        self._iterator = request_iterator

    def _load_all(self):
        self._bytes.seek(0, SEEK_END)
        for chunk in self._iterator:
            self._bytes.write(chunk)

    def _load_until(self, goal_position):
        current_position = self._bytes.seek(0, SEEK_END)
        while current_position < goal_position:
            try:
                current_position += self._bytes.write(next(self._iterator))
            except StopIteration:
                break

    def tell(self):
        return self._bytes.tell()

    def read(self, size=None):
        left_off_at = self._bytes.tell()
        if size is None:
            self._load_all()
        else:
            goal_position = left_off_at + size
            self._load_until(goal_position)

        self._bytes.seek(left_off_at)
        return self._bytes.read(size)

    def seek(self, position, whence=SEEK_SET):
        if whence == SEEK_END:
            self._load_all()
        else:
            self._bytes.seek(position, whence)


def popen(cmd, timeout=15):
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)
    try:
        outs, errs = proc.communicate(timeout=15)
    except subprocess.TimeoutExpired:
        proc.kill()
        outs, errs = proc.communicate()
    return outs, errs


def getchromeversion():
    if sys.platform == "win32":
        chromedirs = [r"%ProgramFiles%\Google\Chrome\Application\chrome.exe",
                      r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe",
                      r"%LocalAppData%\Google\Chrome\Application\chrome.exe"]
        for chromedir in chromedirs:
            outs, errs = popen(["powershell", "-Command", f"(Get-Item \"{os.path.expandvars(chromedir)}\")"
                                                          f".VersionInfo.FileVersion"])
            logger.debug(outs)
            logger.debug(errs)
            if outs and not errs:
                return outs.decode("utf-8").strip()
    else:
        outs, errs = popen(["google-chrome", "-product-version"])
        if outs and not errs:
            return outs.decode("utf-8").strip()
    raise Exception("Failed to detect chrome installation. Do you have it installed at the default paths?")


def getdriverversion():
    cdfile = "chromedriver.exe" if sys.platform == "win32" else "./chromedriver"
    if os.path.isfile(cdfile):
        outs, errs = popen([cdfile, "--version"])
        if outs and not errs:
            return outs.decode("utf-8").strip().split(" ")[1]
    else:
        return None


def updatechromedriver():
    logger.info("checking chrome and ChromeDriver...")
    ver = getchromeversion()
    logger.info(f"chrome {ver}")
    cdver = getdriverversion()
    logger.info(f"chromedriver {cdver}")
    if cdver is None:
        logger.log(25, "ChromeDriver not detected, downloading.")
    else:
        if cdver.split(".")[0] == ver.split(".")[0]:
            logger.info(f"ChromeDriver {cdver} shares major version with chrome {ver}, no need to update.")
            return
        else:
            logger.log(25, f"ChromeDriver {cdver} does not share major version with Chrome {ver}, downloading new "
                           f"driver.")
            if sys.platform == 'win32':
                os.remove("chromedriver.exe")
            else:
                os.remove("chromedriver")
    # find vernum of latest compatible release, thanks google!
    for cdurl in [
        f"https://chromedriver.storage.googleapis.com/LATEST_RELEASE_{ver}",
        f"https://chromedriver.storage.googleapis.com/LATEST_RELEASE_{ver.split('.')[0]}",
        f"https://chromedriver.storage.googleapis.com/LATEST_RELEASE"
    ]:
        cdreq = requests.get(cdurl)
        if cdreq.ok:
            logger.debug(f"{cdurl} is ok")
            bestcdver = cdreq.text
            break
        else:
            logger.debug(f"{cdurl} failed with {cdreq.status_code}")
    else:
        raise Exception("Could not find chromedriver version. is google down?")
    logger.info(f"downloading chromedriver {bestcdver}")
    cdzip = requests.get(f"https://chromedriver.storage.googleapis.com/{bestcdver}/"
                         f"chromedriver_{'win32' if sys.platform == 'win32' else 'linux64'}.zip", stream=True)
    with zipfile.ZipFile(ResponseStream(cdzip.iter_content(64))) as zf:
        if sys.platform == 'win32':
            zf.extract("chromedriver.exe")
        else:
            zf.extract("chromedriver")
            # chmod +x / mark executable
            os.chmod('chromedriver', os.stat('chromedriver').st_mode | 0o111)
    logger.log(35, "Downloaded and extracted new chromedriver!")


def send(driver, cmd, params=None):
    """
    i dont know what this does but it communicates with chrome i think
    its copy/pasted code lol!
    """
    if params is None:
        params = {}
    resource = "/session/%s/chromium/send_command_and_get_result" % driver.session_id
    url = driver.command_executor._url + resource
    body = json.dumps({'cmd': cmd, 'params': params})
    response = driver.command_executor._request('POST', url, body)
    # if response['status']: raise Exception(response.get('value'))
    return response.get('value')


def loadhtml(driver, html):
    """
    loads string html into driver
    :param driver: selenium webdriver
    :param html: string of html
    :return: filename of saved html
    """
    base = "file:///" + os.getcwd().replace("\\", "/")
    # html = html.replace("<base href='./'>", f"<base href='{base}/'>")
    html = f"<base href='{base}/'>" + html
    file = temp_file("html")
    with open(file, "w+", encoding="UTF-8") as f:
        f.write(html)
    driver.get("file:///" + os.path.abspath(file).replace("\\", "/"))
    return file
    # print(json.dumps(html))
    # print(html)
    # html_bs64 = base64.b64encode(html.encode('utf-8')).decode()
    # driver.get("data:text/html;base64," + html_bs64)


def initdriver():
    """
    used by pool workers to initialize the web driver
    :return: the driver, not sure if this is used from the return?
    """
    # tempfiles.tempid = tfid
    global opts
    global driver
    opts = webdriver.ChromeOptions()
    opts.headless = True
    if config.log_level.lower() != "debug":  # switches that disable logging
        opts.add_experimental_option('excludeSwitches', ['enable-logging'])
        opts.add_argument("--log-level=3")
    opts.add_argument('--no-proxy-server')
    opts.add_argument("--window-size=0,0")
    opts.add_argument("--hide-scrollbars")
    opts.add_argument("--headless")
    opts.add_argument("--disable-web-security")
    opts.add_argument("--allow-file-access-from-files")
    opts.add_argument("--allow-file-access-from-file")
    opts.add_argument("--allow-file-access")
    opts.add_argument("--disable-extensions")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--no-sandbox")
    if sys.platform == "win32":
        driver = webdriver.Chrome("chromedriver.exe", options=opts, service_log_path='NUL')
    else:
        if "GOOGLE_CHROME_SHIM" in os.environ:  # if on heroku
            driver = webdriver.Chrome(executable_path=os.environ["GOOGLE_CHROME_SHIM"], options=opts,
                                      service_log_path='/dev/null')
        else:
            driver = webdriver.Chrome("./chromedriver", options=opts, service_log_path='/dev/null')
    driverlogger = logging.getLogger('selenium.webdriver.remote.remote_connection')
    if config.log_level.lower() == "debug":
        driverlogger.setLevel(logging.DEBUG)
    else:
        driverlogger.setLevel(logging.WARNING)
    driver.implicitly_wait(10)
    driver.get("file:///" + os.path.abspath("rendering/warmup.html").replace("\\", "/"))
    while driver.execute_script('return document.readyState;') != "complete":
        time.sleep(0.25)
    return driver


def closedriver():
    """
    close driver
    """
    global driver
    # force kill all processes
    p = psutil.Process(driver.service.process.pid)
    for proc in p.children(recursive=True) + [p]:
        logger.debug(proc)
        p.kill()
    # if this doesn't work and george still accumulates chromes, keep a global list of all created processeses and
    # periodically compare it with a list generated from each chrome instance and kill any extraneous processes.
    driver.quit()


def html2png(html, png):
    """
    uses driver to turn html into a png
    :param html: html string
    :param png: filename to save
    """
    while True:
        try:
            driver.set_window_size(1, 1)
        # sometimes the drivers/chromes can just be killed by the OS or lost or something
        # so this restarts it if necessary
        except (selenium.common.exceptions.InvalidSessionIdException, ConnectionRefusedError,
                urllib3.exceptions.MaxRetryError, selenium.common.exceptions.WebDriverException,
                BrokenProcessPool):
            try:
                closedriver()
            except Exception as e:
                logger.debug(e)
            initdriver()
        else:
            break
    tempfile = loadhtml(driver, html)
    # wait for load just in case
    while driver.execute_script('return document.readyState;') != "complete":
        time.sleep(0.25)
    # for image width based styles, this will be a pixel value. for any other html it will be a blank string. if it's
    # 0px, it tried to get the width before the image loaded and that is no good
    while driver.execute_script(
            "return window.getComputedStyle(document.documentElement).getPropertyValue('--1vw');") == "0px":
        driver.execute_script("document.querySelector(':root').style.setProperty('--1vw', `${document.getElementById('i"
                              "mg').scrollWidth / 100}px`);")
        time.sleep(0.25)
    # driver.execute_script("return window.getComputedStyle(document.documentElement).getPropertyValue('--1vw');")
    for _ in range(4):
        size = driver.execute_script(f"return [document.documentElement.scrollWidth, outerHeight(document.body)];")
        logger.debug(size)
        driver.set_window_size(size[0], size[1])
    logger.debug("running beforerender")
    driver.execute_script("if (typeof beforerender === \"function\") {beforerender()}")
    logging.debug("beforerender complete")
    send(driver, "Emulation.setDefaultBackgroundColorOverride", {'color': {'r': 0, 'g': 0, 'b': 0, 'a': 0}})
    driver.get_screenshot_as_file(png)
    # os.remove(tempfile)

# initdriver()
# with open("captionhtml/motivate.html", 'r', encoding="UTF-8") as file:
#     data = file.read()
# html2png(data, "test.png")
