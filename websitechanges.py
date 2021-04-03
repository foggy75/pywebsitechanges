import sys
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import urllib.request
from urllib.parse import urlparse

# install with
# python3 -m pip install click numpy loguru scikit-image opencv-python
import click
from skimage.metrics import structural_similarity as ssim
import cv2
import numpy as np
from loguru import logger

# use hosts file to remove ads for more reproducible websites
hostsfile = "http://sbc.io/hosts/alternates/fakenews-gambling-porn-social/hosts"

indexjs = r"""
const fs = require('fs');

const puppeteer = require('puppeteer');

hosts = {};
//now we read the host file
var hostFile = fs.readFileSync('hosts', 'utf8').split('\n');
var hosts = {};
for (var i = 0; i < hostFile.length; i++) {
    if (hostFile[i].charAt(0) == "#") {
        continue
    }
    var frags = hostFile[i].split(' ');
    if (frags.length > 1 && frags[0] === '0.0.0.0') {
        hosts[frags[1].trim()] = true;
    }
}

(async () => {

    const browser = await puppeteer.launch({ headless: true });
    const page = await browser.newPage();
    await page.setRequestInterception(true)

    page.on('request', request => {

        var domain = null;
        var frags = request.url().split('/');
        if (frags.length > 2) {
            domain = frags[2];
        }

        // just abort if found
        if (hosts[domain] === true) {
            request.abort();
        } else {
            request.continue();
        }
    });
    // Adjustments particular to this page to ensure we hit desktop breakpoint.
    page.setViewport({ width: 1000, height: 1000, deviceScaleFactor: 1 });

    await page.goto(process.argv[2], { waitUntil: 'networkidle2' });
    // get rid of cookie consent pop-ups
    // thanks to: https://stackoverflow.com/questions/59618456/pupeteer-how-can-i-accept-cookie-consent-prompts-automatically-for-any-url
    await page.evaluate(_ => {
        var xcc
        // ids
        var xcc_id = [
            'cookie-apply-all',
            'cookie-settings-all',
            // add ids here
        ];
        for (let i = 0; i < xcc_id.length; i++) {
            xcc = document.getElementById(xcc_id[i]);
            if (xcc != null) {
                xcc.click();
            }
        }
        // classes
        var xcc_class = [
            'accept-all',
            'accept-cookies-button',
            'avia-cookie-select-all',
            'js-confirm-button',
            // add classes here
        ];
        for (let i = 0; i < xcc_class.length; i++) {
            xcc = document.getElementsByClassName(xcc_class[i]);
            if (xcc != null && xcc.length != 0) {
                xcc[0].click();
            }
        }
    
        // custom data attributes
        xcc = document.querySelectorAll('button[name=accept_cookie]'); if (xcc != null && xcc.length != 0) { xcc[0].click(); }
        xcc = document.querySelectorAll('[data-cookieman-accept-all]'); if (xcc != null && xcc.length != 0) { xcc[0].click(); }
        xcc = document.querySelectorAll('div.VfPpkd-RLmnJb'); if (xcc != null && xcc.length != 0) { xcc[0].click(); }

         // hide iframes, can't eval
        xcc = document.querySelectorAll("iframe[src*=eurocookie]"); if (xcc != null && xcc.length != 0) { xcc[0].style.display = 'none'; }
        xcc = document.querySelectorAll("iframe[src*=eurocookie]"); if (xcc != null && xcc.length > 1) { xcc[1].style.display = 'none'; }
    }).catch((err) => {
        console.log('!!! await cookies exception caught:');
        console.log(err.message);
    });
    await page.waitForTimeout(15000);

    if (process.argv[4] == 'full') {
        await page.screenshot({
            path: process.argv[3],
            fullPage: true
        })
        await browser.close();
        return
    }
    /**
     * Takes a screenshot of a DOM element on the page, with optional padding.
     *
     * @param {!{path:string, selector:string, padding:(number|undefined)}=} opts
     * @return {!Promise<!Buffer>}
     */
    async function screenshotDOMElement(opts = {}) {
        const padding = 'padding' in opts ? opts.padding : 0;
        const path = 'path' in opts ? opts.path : null;
        const selector = opts.selector;

        if (!selector)
            throw Error('Please provide a selector.');

        const rect = await page.evaluate(selector => {
            const element = document.querySelector(selector);
            if (!element)
                return null;
            const { x, y, width, height } = element.getBoundingClientRect();
            return { left: x, top: y, width, height, id: element.id };
        }, selector);

        if (!rect)
            throw Error(`Could not find element that matches selector: ${selector}.`);

        return await page.screenshot({
            path,
            clip: {
                x: rect.left - padding,
                y: rect.top - padding,
                width: rect.width + padding * 2,
                height: rect.height + padding * 2
            }
        }).catch((err) => {
            console.log('!!! await page.screenshot exception caught:');
            console.log(err.message);
        });
    }

    await screenshotDOMElement({
        path: process.argv[3],
        selector: process.argv[4],
        padding: 0
    }).catch((err) => {
        console.log('!!! await screenshotDOMElement exception caught:');
        console.log(err.message);
    });

    browser.close();
})();
"""


def compare_images(previous, current, result):
    before = cv2.imread(previous)
    after = cv2.imread(current)

    # Convert images to grayscale
    before_gray = cv2.cvtColor(before, cv2.COLOR_BGR2GRAY)
    after_gray = cv2.cvtColor(after, cv2.COLOR_BGR2GRAY)

    # Compute SSIM between two images
    try:
        (score, diff) = ssim(before_gray, after_gray, full=True)
    except ValueError as e:
        if "{}".format(e) == "Input images must have the same dimensions.":
            # images are different
            cv2.imwrite(result, after, [int(cv2.IMWRITE_JPEG_QUALITY), 50])
            return 0
        else:
            raise e

    # The diff image contains the actual image differences between the two images
    # and is represented as a floating point data type in the range [0,1]
    # so we must convert the array to 8-bit unsigned integers in the range
    # [0,255] before we can use it with OpenCV
    diff = (diff * 255).astype("uint8")

    # Threshold the difference image, followed by finding contours to
    # obtain the regions of the two input images that differ
    thresh = cv2.threshold(diff, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)[1]
    contours = cv2.findContours(
        thresh.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )
    contours = contours[0] if len(contours) == 2 else contours[1]

    mask = np.zeros(before.shape, dtype="uint8")
    filled_after = after.copy()

    for c in contours:
        area = cv2.contourArea(c)
        if area > 40:
            x, y, w, h = cv2.boundingRect(c)
            cv2.rectangle(before, (x, y), (x + w, y + h), (36, 255, 12), 2)
            cv2.rectangle(after, (x, y), (x + w, y + h), (36, 255, 12), 2)
            cv2.drawContours(mask, [c], 0, (0, 255, 0), -1)
            cv2.drawContours(filled_after, [c], 0, (0, 255, 0), -1)

    filename = "diff_previous_" + previous
    cv2.imwrite(filename, before)
    filename = "diff_current_" + current
    cv2.imwrite(filename, after)
    cv2.imwrite(result, after, [int(cv2.IMWRITE_JPEG_QUALITY), 50])
    # cv2.imshow('after', after)
    # cv2.imshow('diff',diff)
    # cv2.imshow('mask',mask)
    # cv2.imshow('filled after',filled_after)
    # cv2.waitKey(0)
    return score


def send_email(smtpemail, smtppass, to, subject, body, imgname):
    img_data = open(imgname, "rb").read()
    msg = MIMEMultipart()
    msg["Subject"] = subject
    msg["From"] = smtpemail
    msg["To"] = to

    text = MIMEText(body)
    msg.attach(text)
    image = MIMEImage(img_data, name=os.path.basename(imgname))
    msg.attach(image)

    s = smtplib.SMTP("smtp.gmail.com", "587")
    s.ehlo()
    s.starttls()
    s.ehlo()
    s.login(smtpemail, smtppass)
    s.sendmail(msg["From"], msg["To"], msg.as_string())
    s.quit()


@click.command()
@click.option("--folder", default=".", help="directory to store data")
@click.option("--url", help="url to watch", required=True)
@click.option("--css", default="full", help="CSS selector of element to watch, default full page")
@click.option("--to", help="email address of person to alert")
@click.option("--smtpemail", default="", help="SMTP email address")
@click.option("--smtppass", default="", help="SMTP email password")
@click.option("--threshold", default=1.0, help="threshold for sending email")
@click.option("--tag", default="", help="tag to be used in email header")
@click.option("--doublecheck", is_flag=True, default=False, help="double-check when a new change was detected, to avoid false alarms")
def run(folder, url, css, to, smtpemail, smtppass, threshold, tag, doublecheck):
    logger.debug("changing dir to {}", folder)
    os.chdir(folder)
    with open("index.js", "w") as f:
        f.write(indexjs)
    if not os.path.exists(os.path.join("node_modules", "puppeteer")):
        logger.debug("installing puppeteer in {}", os.path.abspath("."))
        os.system("npm i puppeteer")
    if not os.path.exists(os.path.join("hosts")):
        logger.debug("downloading hosts file {}", hostsfile)
        urllib.request.urlretrieve(hostsfile, "hosts")
    if not tag:
        tag = urlparse(url).netloc
    logger.debug("using tag: {} - doublecheck enabled: {}", tag, str(doublecheck))
    new_png = tag + "_new.png"
    last_png = tag + "_last.png"
    after_jpg = tag + "_after.jpg"
    loopCount = 1
    if doublecheck:
        loopCount = 2
    for x in range(loopCount):
        node_cmd = "node index.js " + url + " " + new_png + " '" + css + "'"
        logger.debug(node_cmd)
        
        os.system(node_cmd)
        if not os.path.exists(new_png):
            # no new screenshot; abort
            logger.debug("Aborting - no new screenshot available to compare!")
            break
        if os.path.exists(last_png):
            logger.debug("comparing images")
            similarity = compare_images(last_png, new_png, after_jpg)
            logger.debug("similarity: {}", similarity)
            if similarity < threshold and smtpemail != "" and smtppass != "" and to != "":
                if doublecheck and x == 0:
                    # first try, re-check
                    logger.debug("similarity < " + str(threshold) + ", will double-check")
                    continue
                logger.debug("similarity < " + str(threshold) + ", sending email")
                logger.debug(os.path.join(os.path.abspath("."), after_jpg))
                subj = "Change detected for " + tag + " @ " + datetime.now().strftime("%m/%d/%Y %H:%M") + " #WebChange"
                send_email(
                    smtpemail,
                    smtppass,
                    to,
                    subj,
                    url,
                    os.path.join(os.path.abspath("."), after_jpg),
                )
            else:
                # no change, we're done
                break

    if os.path.exists(last_png):
        os.remove(last_png)
    if os.path.exists(new_png):
        logger.debug("saving new image")
        os.rename(new_png, last_png)


if __name__ == "__main__":
    run()
