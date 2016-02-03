# smsgateway
smsgateway supporting portech gsm gateway

This script is able to communicate with Portech GSM gateways (tested on MV370), and send single SMS or fetch mails and transforms 
it to SMS. It uses the python-messaging package for PDU encodings

## Usage :
* smsgateway.py imap2sms
* smsgateway.py sms <number> <message>
* smsgateway.py clearallsms


## Requirements :
python-messaging available on : [pmarti/python-messaging](https://github.com/pmarti/python-messaging)
