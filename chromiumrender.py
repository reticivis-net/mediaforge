import json
import logging
import os
import sys
import time

import selenium.common
import urllib3

from tempfiles import temp_file
from selenium import webdriver
import config


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
    # https://chromedriver.storage.googleapis.com/index.html?path=87.0.4280.88/
    if sys.platform == "win32":
        driver = webdriver.Chrome(config.chrome_driver_windows, options=opts, service_log_path='NUL')
    else:
        driver = webdriver.Chrome(config.chrome_driver_linux, options=opts, service_log_path='/dev/null')
    logger = logging.getLogger('selenium.webdriver.remote.remote_connection')
    logger.setLevel(logging.WARNING)
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
    driver.close()


def html2png(html, png):
    """
    uses driver to turn html into a png
    :param html: html string
    :param png: filename to save
    """
    while True:
        try:
            driver.set_window_size(1, 1)
        # sometimes the drivers/chromes can just be killed by the OS so this restarts it if necessary
        except (selenium.common.exceptions.InvalidSessionIdException, ConnectionRefusedError,
                urllib3.exceptions.MaxRetryError):
            try:
                driver.close()
            except:
                pass
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
        driver.set_window_size(size[0], size[1])
    driver.execute_script("if (typeof beforerender === \"function\") {beforerender()}")
    send(driver, "Emulation.setDefaultBackgroundColorOverride", {'color': {'r': 0, 'g': 0, 'b': 0, 'a': 0}})
    driver.get_screenshot_as_file(png)
    # os.remove(tempfile)

# initdriver()
# with open("captionhtml/motivate.html", 'r', encoding="UTF-8") as file:
#     data = file.read()
# html2png(data, "test.png")
