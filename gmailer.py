#!/usr/bin/python

import smtplib
from email.MIMEMultipart import MIMEMultipart
from email.MIMEBase import MIMEBase
from email.MIMEText import MIMEText
from email import Encoders
import os
import logging

GMAIL_SETTINGS = {
    'user': '', # whatever@gmail.com,
    'password': '', # password for whatever@gmail.com
}


def mail(to, subject, text, attach=None, html=None, pre=False):
    msg = MIMEMultipart()
    
    msg['From'] = GMAIL_SETTINGS['user']
    msg['To'] = to
    msg['Subject'] = subject
    
    
    # Encapsulate the plain and HTML versions of the message body in an
    # 'alternative' part, so message agents can decide which they want to display.
    
    if pre:
        html ="<pre>%s</pre>" % text
    if html:
        msgAlternative = MIMEMultipart('alternative')
        msg.attach(msgAlternative)
        
        msgText = MIMEText(text)
        msgAlternative.attach(msgText)
        
        # We reference the image in the IMG SRC attribute by the ID we give it below
        msgText = MIMEText(html, 'html')
        msgAlternative.attach(msgText)
    else:
        msg.attach(MIMEText(text))
    
    
    if attach:
        part = MIMEBase('application', 'octet-stream')
        part.set_payload(open(attach, 'rb').read())
        Encoders.encode_base64(part)
        part.add_header('Content-Disposition',
                'attachment; filename="%s"' % os.path.basename(attach))
        msg.attach(part)
    mailServer = smtplib.SMTP("smtp.gmail.com", 587)
    mailServer.ehlo()
    mailServer.starttls()
    mailServer.ehlo()
    mailServer.login(GMAIL_SETTINGS['user'], GMAIL_SETTINGS['password'])
    
    mailServer.sendmail(GMAIL_SETTINGS['user'], to, msg.as_string())

    mailServer.close()

# mail("kortina@gmail.com",
#    "Hello from python!",
#    "This is a email sent with python",
#   "my_picture.jpg")
