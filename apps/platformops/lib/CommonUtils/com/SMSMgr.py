''''*******************************************************************************************************************
* Copyright         : PlatformOps
* File Name         : SMSMgr.py
* Description       : Common Utility Module sending SMS
*
* Revision History  :
* Date				Author    		        Comments
* ---------------------------------------------------------------------------------------------------------------------
* 02-Jan-25 		Sandeep Mahajan		     Created.
*
*********************************************************************************************************************'''
import os
from CommonUtils.logs.AppLogging import utils_logger


def cutil_send_sms(send_number, receiver_number, msg):
    utils_logger.debug(f"cutil_send_sms, send_number, receiver_number, msg: {send_number, receiver_number, msg}")
    return

