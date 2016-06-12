import feedparser
import urllib.request
import subprocess
import sys, traceback
import os.path
import smtplib
import mimetypes
import configparser
import shelve
import time
import logging

FORMAT = '%(asctime)-15s %(message)s'
logging.basicConfig(filename='trace.log', level=logging.INFO, format=FORMAT)
logging.basicConfig(filename='trace.log', level=logging.ERROR, format=FORMAT)

from email import encoders
from email.message import Message
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart

from urllib.parse import urlparse
import codecs

from lxml import etree
from io import StringIO

def check_feeds():
    logging.info('****************Feeds check is started****************')
    feeds = config['Feeds']
    try:
        for (feed_name, url) in feeds.items():
            logging.info('********************************Check {0} feed is started********************************'.format(feed_name))
            feed_entries = read_downloaded_feed_entries(feed_name)
            rss = feedparser.parse(url)
            new_feed_entries = get_new_feed_entries(rss.entries, feed_entries)
            logging.info('{0} new feeds'.format(len(new_feed_entries)))
            for feed_entry in new_feed_entries:
                logging.info('feed: {0}'.format(feed_entry.title))
                file_url = get_file_url(feed_entry.link)
                logging.info('downloading file: {0}'.format(file_url))
                file_path = download_file(file_url, feed_name)
                logging.info('converting file...')
                converted_file_path = convert_file(file_path)
                time.sleep(int(base_settings['WaitTimeToSendEmail']))
                logging.info('sending file...')
                #send_email(converted_file_path)
                feed_entries.append(feed_entry.link)
                logging.info('saving downloaded feed entry')
                save_feed_entries(feed_name, feed_entries)
                sys.exit()
            logging.info('********************************Check {0} feed is completed********************************'.format(feed_name))
    except Exception as ex:
        logging.info('Exception has been raised')
        logging.exception(ex)
    logging.info('****************Feeds check is completed****************')

def read_downloaded_feed_entries(name):     
    with shelve.open('feeds') as db:
        if name in db.keys():
            return db[name]
        else:
            return []

def save_feed_entries(feed_name, feed_entries):
    with shelve.open('feeds') as db:
        db[feed_name] = feed_entries			
            
def get_new_feed_entries(rss_entries, downloaded_entries):
    return [entry for entry in rss_entries if entry.link not in downloaded_entries]
        
def get_file_url(feed_entry_url):
    url = urlparse(feed_entry_url)
    feed_entry_url_path = urllib.parse.quote(codecs.encode(url.path,'utf-8'))
    url_template = '{0}://{1}{2}'
    #print(feed_entry_url)
    #print(urllib.parse.quote(feed_entry_url))
    #url = urlparse(urllib.parse.quote(feed_entry_url))
    #print(url.scheme + '://' + url.netloc + feed_entry_url_path )
    #sys.exit()
    #print(urllib.parse.quote(feed_entry_url))
    with urllib.request.urlopen(url_template.format(url.scheme, url.netloc, feed_entry_url_path)) as f:
        response = f.read()
    html_string = str(response, 'utf-8')
    
    parser = etree.HTMLParser()
    
    tree = etree.parse(StringIO(html_string), parser)
    downloadLinks = tree.xpath('.//div[@class="linkList download"]/a/@href')
    if len(downloadLinks) == 0:
        intern_link = tree.xpath('.//div[@class="linkList intern"]/a/@href')[0]
        feed_entry_url_path = urllib.parse.quote(codecs.encode(intern_link,'utf-8'))
        with urllib.request.urlopen(url_template.format(url.scheme, url.netloc, feed_entry_url_path)) as f:
            response = f.read()
        html_string = str(response, 'utf-8')
        parser = etree.HTMLParser()
        tree = etree.parse(StringIO(html_string), parser)
        file_url = tree.xpath('.//div[@class="linkList download"]/a/@href')[0]
    else:
        file_url = downloadLinks[0]
    
    return url_template.format(url.scheme, url.netloc, file_url)

def download_file(file_url, feed_name):
    with urllib.request.urlopen(file_url) as f:
        response = f.read()
    
    folder_name = base_settings['FolderName']
	
    if not os.path.exists(folder_name):
        os.mkdir(folder_name)
        
    dir =  '{0}\\{1}\\'.format(folder_name, feed_name)
    if not os.path.exists(dir):
        os.mkdir(dir)
	
    file_name = os.path.basename(file_url)
    file_path = dir + file_name
    with open(file_path, "wb+") as f:
        f.write(response)
		
    return file_path

def convert_file(file_path):
    converted_file_path = '{0}.azw3'.format(os.path.splitext(file_path)[0])
    subprocess.run(["ebook-convert", file_path,
                converted_file_path,
                "--enable-heuristics", "--search-replace", "dw_pdf_convert.csr"])
    return converted_file_path

def send_email(file_path):
    
    smtp_server = smtp_settings['Server']
    smtp_port = smtp_settings['Port']
    email_settings = config['EmailSettings']
    subject = email_settings['Subject']
    sender_email = email_settings['SenderEmail']
    recipient_email = email_settings['RecipientEmail']
    password = email_settings['Password']

    message = MIMEMultipart()
    message['Subject'] = subject
    message['To'] = recipient_email
    message['From'] = sender_email
    
    file_name = os.path.basename(file_path)
    with open(file_path, 'rb') as fp:
        msg = MIMEBase(None, None)
        msg.set_payload(fp.read())

    encoders.encode_base64(msg)
    msg.add_header('Content-Disposition', 'attachment', filename = file_name)
    message.attach(msg)
    composed = message.as_string()	
    with smtplib.SMTP(smtp_server, smtp_port) as s:
        s.starttls()
        s.login(sender_email, password)
        s.sendmail(sender_email, recipient_email, composed)

config = configparser.ConfigParser()
config.read('config.ini')

base_settings = config['BaseSettings']
smtp_settings = config['SmtpSettings']
check_feeds()