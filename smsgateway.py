#!/usr/bin/env python2.7
# -*- encoding: utf-8 -*-

import imaplib
import email
import time
import telnetlib
import config
import fcntl
import sys

from email.header import decode_header
from messaging.sms import SmsSubmit


def csv_config_parser(mailboxes):
    """
    Reads CSV config, returns as a list
    :param mailboxes:
    :return:
    """
    params = []
    with open(mailboxes) as f:
        for line in f:
            if "#" in line:
                pass
            else:
                tmp_str = line.strip("\n").split(",")
                params.append(tmp_str)
    return params


def fetch_unread_mails(mailboxserver, mailboxlogin, mailboxpassword):
    """
    Fetch unread emails on specific mailbox, and returns some fields
    :param mailboxserver:
    :param mailboxlogin:
    :param mailboxpassword:
    :return str:
    """
    mail = imaplib.IMAP4_SSL(mailboxserver)
    mail.login(mailboxlogin, mailboxpassword)
    mail.list()
    mail.select("INBOX")

    mails = []

    n = 0
    returncode, messages = mail.search(None, '(UNSEEN)')
    if returncode == 'OK':
        for num in messages[0].split():
            n += 1
            typ, data = mail.fetch(num, 'RFC822')
            for response_part in data:
                if isinstance(response_part, tuple):
                    original = email.message_from_string(response_part[1])
                    mailfrom = original['From']
                    if "<" in mailfrom:
                        mailfrom = mailfrom.split('<')[1].rstrip('>')
                    mailsubject = original['Subject']
                    mailsubject = decode_header(mailsubject)
                    default_charset = 'ASCII'
                    mailsubject = ''.join([unicode(t[0], t[1] or default_charset) for t in mailsubject])
                    mails.append([mailfrom, mailsubject])
    return mails


def clear_all_sms():
    """
    Clears all stored SMS on Portech like gateways
    :return: None
    """
    try:
        count = 0
        tn = telnetlib.Telnet(config.smshost, 23)
        tn.read_until("username: ")
        tn.write(config.smsusername + "\r\n")
        tn.write(config.smspassword + "\r\n")
        tn.read_until("user level = admin.")
        tn.write("module1\r\n")
        tn.read_until("got!! press 'ctrl-x' to release module 1.")
        while count < 100:
            tn.write("AT+CMGD=" + str(count) + "\r\n")
            count += 1
            tn.read_until("\r\n")
        tn.close()
    except:
        print("Unexpected error:", sys.exc_info()[0])
        raise


def resize_ascii_sms(message):
    """
    Strip message if longer than config.smssize
    :param message: Message to resize
    :return message: Resized message
    """
    value = config.smssize-3
    if len(message) > value:
        message = message[:value]
    return message


def resize_pdu_sms(message):
    """
    Strip SMS if longer than config.smssize
    :param message: Message to resize
    :return message: Resized message
    """
    if len(message) > config.smssize:
            message = message[:config.smssize]
    return message


def sms_template(sender, subject):
    """
    Uses a template to make a short message from email fields
    :param sender: str
    :param subject: str
    :return:
    """
    text = config.smstemplate % (sender, subject)
    return text


def imap2sms(conf):
    """
    Send a sms
    :param conf:
    :return:
    """
    for l in conf:
        username = l[0]
        password = l[1]
        mailserver = l[2]
        numbers = []
        i = 3
        while i < len(l):
            numbers.append(l[i])
            i += 1

        mails = fetch_unread_mails(username, password, mailserver)
        for number in numbers:
            for mail in mails:
                sender = mail[0]
                subject = mail[1]
                if config.smsformat == "pdu":
                    sms = resize_pdu_sms(sms_template(sender, subject))
                    pdustring, pdulength = pduformat(number, sms)
                    send_pdu_sms(pdustring, pdulength)
                elif config.smsformat == "ascii":
                    sms = resize_ascii_sms(sms_template(sender, subject))
                    send_ascii_sms(number, sms)


def pduformat(phonenumber, message):
    """
    Formats SMS using pdu encoding
    :param phonenumber: Phone number to insert in pdu
    :param message: Text message
    :return: pdustring, pdulenght
    """
    sms = SmsSubmit(phonenumber, message)
    pdu = sms.to_pdu()[0]
    pdustring = pdu.pdu
    pdulength = pdu.length
    # debug output
    # print(phonenumber, message)
    # print(pdu.length, pdu.pdu)
    return pdustring, pdulength


def send_ascii_sms(phonenumber, sms):
    """
    Send SMS using telnetlib, returns exception when issues with telnet communication
    :param phonenumber: Phone number to insert in pdu
    :param sms: Text message
    """
    decoded_sms = sms.encode("ascii", "ignore")
    try:
        time.sleep(2)
        tn = telnetlib.Telnet(config.smshost, 23)
        tn.read_until("username: ")
        tn.write(config.smsusername + "\r\n")
        tn.write(config.smspassword + "\r\n")
        tn.read_until("user level = admin.")
        tn.write("state1\r\n")
        tn.read_until("module 1: free.\r\n]")
        tn.write("module1\r\n")
        tn.read_until("got!! press 'ctrl-x' to release module 1.")
        tn.write("AT+CMGF=1\r\n")
        tn.read_until("0\r\n")
        tn.write('AT+CMGS=%s\r\n' % phonenumber)
        tn.read_until("> ")
        tn.write("%s\x1A" % decoded_sms)
        tn.read_until("+CMGS")
        tn.close()
    except:
        print("Unexpected error :", sys.exc_info()[0])
        raise


def send_pdu_sms(pdustring, pdulength):
    """
    Send SMS using telnetlib, returns exception when issues with telnet communication
    :param pdustring: is the converted sms to pdu format
    :param pdulength: is the size of the pdustring
    """
    try:
        time.sleep(2)
        tn = telnetlib.Telnet(config.smshost, 23)
        tn.read_until("username: ")
        tn.write(config.smsusername + "\r\n")
        tn.write(config.smspassword + "\r\n")
        tn.read_until("user level = admin.")
        tn.write("state1\r\n")
        tn.read_until("module 1: free.\r\n]")
        tn.write("module1\r\n")
        tn.read_until("got!! press 'ctrl-x' to release module 1.")
        tn.write("AT+CMGF=0\r\n")
        tn.read_until("0\r\n")
        tn.write('AT+CMGS=%s\r\n' % pdulength)
        tn.read_until("> ")
        tn.write("%s\r\n\x1A" % pdustring)
        tn.read_until("+CMGS")
        tn.close()
    except:
        print("Unexpected error:", sys.exc_info()[0])
        raise


def usage():
    """
    Prints usage
    :return: str
    """
    usagetext = "smsgateway.py subcommands : \n\n%s imap2sms\n%s sms <number> <message>\n%s clearallsms\n" % (
        sys.argv[0], sys.argv[0], sys.argv[0])
    return usagetext


def debug():
    """
    Debug Function
    :return: bool
    """
    return True


fh = open(config.pidfile, 'w')
try:
    fcntl.lockf(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
except IOError:
    # another instance is running
    print 'Error: Another instance is running...'
    sys.exit(0)

if len(sys.argv) > 1:
    if sys.argv[1] == "clearallsms":
        clear_all_sms()

    elif sys.argv[1] == "sms":
        if len(sys.argv) == 4:
            phonenumber = sys.argv[2]
            sms = sys.argv[3]
            pdustring, pdulength = pduformat(phonenumber, sms)
            if config.smsformat == "pdu":
                send_pdu_sms(pdustring, pdulength)
            elif config.smsformat == "ascii":
                send_ascii_sms(phonenumber, sms)
        else:
            print(usage())

    elif sys.argv[1] == "imap2sms":
        config_params = csv_config_parser(config.mailboxes)
        imap2sms(config_params)

    elif sys.argv[1] == "debug":
        print debug()
else:
    print(usage())
    exit(1)
