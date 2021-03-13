# websitechanges

A simple python script to email you whenever a website changes.

## Install

First install Node and Python 3.x on your system if you don't have it already. Then you will need the required packages which can be installed with `pip`:

	python3 -m pip install click numpy loguru scikit-image opencv-python

Then get the script:

	wget https://raw.githubusercontent.com/foggy75/pywebsitechanges/master/websitechanges.py

And now run it wherever - in a folder, in a cron, etc.

## Usage

```bash
$ python3 websitechanges.py --help
Usage: websitechanges.py [OPTIONS]

Options:
  --url TEXT         url to watch  [required]
  --folder TEXT      directory to store data
  --css TEXT         CSS selector of element to watch, default full page
  --to TEXT          email address of person to alert
  --smtpemail TEXT   SMTP gmail email address
  --smtppass TEXT    SMTP gmail password (use an app password)
  --threshold FLOAT  threshold before sending email (result ranges from 0.0 to 1.0)
  --tag              tag to use in the email subject
```

The `url` is the specified URL.

The `folder` specifies where to store all the data and puppeteer information. This location will also be used to store the puppeteer and chromium headless packages.

The `css` will take a CSS query for a specific element you want to view. If omitted, it will capture the whole page. Puppeteer allows to use either [css selectors](https://www.w3schools.com/cssref/css_selectors.asp) or xpath syntax.

To be alerted you will need to set `to` (the email to alert), `smtpemail` (the email sign-in for the SMTP), and `smtppass` (the password for the SMTP). You can easily setup a Gmail account to be used as an SMTP provider. 

### Example

The simplest way to run is:

	python3 websitechanges.py --url SOMEURL

This will automatically download puppeteer, which is used to gather the screenshot. It will also download a HOSTS file to block ads so that the website can be shown reproducibly. 

Every alert will send you an image of the latest image, in low quality JPEG format in order to save on bandwidth.

Each time the script will only run once, so you will need to set up a cron job or a loop in a script to keep it continually running:
```bash
#!/bin/bash

while [ 1 ]
do
	python3 websitechanges.py --url SOMEURL
	sleep 30m
done
```

## License

MIT