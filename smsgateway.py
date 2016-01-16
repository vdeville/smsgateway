#!/usr/bin/env python
# -*- encoding: utf-8 -*-

import imaplib
import email
import time
import telnetlib
import config
import fcntl
import sys
import unicodedata

from email.header import decode_header
from messaging.sms import SmsSubmit

def fetch_unread_mails():
	"""Fetch unread emails on specific mailbox, and returns some fields"""
	mail = imaplib.IMAP4_SSL(config.mailboxserver)
	mail.login(config.mailboxlogin,config.mailboxpassword)
	mail.list()
	status,messages = mail.select("INBOX")

	mails=[]

	n=0
	retcode, messages = mail.search(None, '(UNSEEN)')
	if retcode == 'OK':
		for num in messages[0].split():
			n=n+1
			typ,data = mail.fetch(num,'RFC822')
			for response_part in data:
				if isinstance(response_part,tuple):
					original = email.message_from_string(response_part[1])
					mailfrom = original['From']
					if "<" in mailfrom:
						mailfrom = mailfrom.split('<')[1].rstrip('>')
					mailsubject = original['Subject']
					mailsubject = decode_header(mailsubject)
					default_charset = 'ASCII'
					mailsubject=''.join([ unicode(t[0], t[1] or default_charset) for t in mailsubject ])
					mails.append([mailfrom,mailsubject])
	return mails

def clearallsms():
	"""Clears all stored SMS on Portech like gateways"""
	try:
		count=0
		tn = telnetlib.Telnet(config.smshost,23)
		tn.read_until("username: ")
		tn.write(config.smsusername + "\r\n")
		tn.write(config.smspassword + "\r\n")
		tn.read_until("user level = admin.")
		tn.write("module1\r\n")
		tn.read_until("got!! press 'ctrl-x' to release module 1.")
		while count<100:
			tn.write("AT+CMGD="+str(count)+"\r\n")
			count=count+1
			tn.read_until("\r\n")
		tn.close()
	except:
		print("Unexpected error:", sys.exc_info()[0])
		raise

def formatsms(message):
	"""Strip SMS if longer than config.smssize"""
        if len(message) > config.smssize:
                message = message[:config.smssize]
        return message

def imap2sms(sender,subject):
	"""Uses a template to make a short message from email fields"""
	sms=config.smstemplate % (sender,subject)
	return sms

def pduformat(phonenumber,message):
	"""Formats SMS using pdu encoding"""
	sms = SmsSubmit(phonenumber, message)
	pdu = sms.to_pdu()[0]
	pdustring=pdu.pdu
	pdulength=pdu.length
	# debug output
	#print(phonenumber, message)
	#print(pdu.length, pdu.pdu)
	return pdustring,pdulength

def sendsms(pdustring,pdulenght):
	"""Send SMS using telnetlib, returns exception when issues with telnet communication"""
	try:
		time.sleep(2)
		tn = telnetlib.Telnet(config.smshost,23)
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
		tn.write("%s\x1A" % pdustring)
		tn.read_until("+CMGS")
		tn.close()
	except:
		print("Unexpected error:", sys.exc_info()[0])
		raise

def usage():
	"""Prints usage"""
	usage="smsgateway.py subcommands : \n\n%s imap2sms\n%s sms <number> <message>\n%s clearallsms\n" % (sys.argv[0],sys.argv[0],sys.argv[0])
	return usage

fh = open(config.pidfile, 'w')
try:
	fcntl.lockf(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
except IOError:
	# another instance is running
	print 'Error: Another instance is running...'
	sys.exit(0)

if len(sys.argv) > 1:
	if sys.argv[1] == "clearallsms":
		clearallsms()
	elif sys.argv[1] == "sms":
		if (len(sys.argv)==4):
			phonenumber=sys.argv[2]
			sms=sys.argv[3]
			pdustring,pdulength=pduformat(phonenumber,sms)
			sendsms(pdustring,pdulength)
		else:
			print(usage())
	elif sys.argv[1] == "imap2sms":
		mails = fetch_unread_mails()
		for phonenumber in config.smsrecipients:
			for mail in mails:
				sender=mail[0]
				subject=mail[1]
				sms=formatsms(imap2sms(sender,subject))
				pdustring,pdulength=pduformat(phonenumber,sms)
				sendsms(pdustring,pdulength)
else:
	print(usage())
	exit(1)
