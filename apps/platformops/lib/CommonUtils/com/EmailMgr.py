''''*******************************************************************************************************************
* Copyright         : PlatformOps
* File Name         : EmailMgr.py
* Description       : Common Utility Module sending Email
*
* Revision History  :
* Date				Author    		        Comments
* ---------------------------------------------------------------------------------------------------------------------
* 15-June-23 		Yogita		            Created.
* 02-Jan-25 		Sandeep Mahajan		    Updated
* 10-Jan-25         Sumit Das               Updated
*********************************************************************************************************************'''

# Import System Modules
import os
import smtplib
from email import encoders
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from CommonUtils.CutilSetting import CutilSettings
from email.mime.multipart import MIMEMultipart
from CommonUtils.logs.AppLogging import utils_logger


""" ********************************************** Helper Functions ********************************************** """


def _validate_smtp_config():
    if not CutilSettings.mail_host or not CutilSettings.mail_port or \
            not CutilSettings.mail_username or not CutilSettings.mail_password:
        return False
    return True


def _validate_attachments(attachments):

    # Check if the attachments list is empty
    if not attachments:
        return True

    for attachment in attachments:
        if not os.path.isfile(attachment):
            return False
    return True


def _validate_recipient_list(mail_tolist):

    # Check mail_tolist list is npt empty !
    if not mail_tolist:
        return False
    return True


def _msg_append_attachments(msg, attachments):

    # Check mail_tolist list is npt empty !
    for attachment in attachments:
        part = MIMEBase('application', 'octet-stream')
        try:
            with open(attachment, "rb") as file:
                part.set_payload(file.read())
                encoders.encode_base64(part)
                part.add_header('Content-Disposition', f'attachment; filename={os.path.basename(attachment)}')
                msg.attach(part)
        except Exception as e:
            utils_logger.debug(f"Error reading attachment {attachment}: {e}")
            return False, msg

    return True, msg


def _validate_mail_info(mail_tolist,attachments):
    # Validate SMTP configuration is initialized already !
    if not _validate_smtp_config():
        utils_logger.debug(f"Email Send Failure, Email Module Setting not initialized !")
        return False, 'Email Module Setting not initialized!'

    # Validate recipient list
    if not _validate_recipient_list(mail_tolist):
        utils_logger.debug(f"Email Send Failure, Recipient List cannot be empty.!")
        return False, 'Email Send Failure, Recipient List cannot be empty.!'

    # Validate attachments
    if not _validate_attachments(attachments):
        utils_logger.debug(f"Invalid Attachments, some of files may not be present !")
        return False, 'Invalid Attachments, some of files may not be present!'

    return True, ""


def _send_email(mail_tolist, msg):
    # Sending email
    try:
        with smtplib.SMTP(CutilSettings.mail_host, CutilSettings.mail_port) as server:
            if CutilSettings.mail_use_tls:
                server.starttls()
            server.login(CutilSettings.mail_username, CutilSettings.mail_password)
            server.sendmail(CutilSettings.mail_username, mail_tolist, msg.as_string())
    except smtplib.SMTPException as e:
        error_msg = f"SMTP error: {e}"
        utils_logger.debug(error_msg)
        return False, error_msg
    except Exception as e:
        error_msg = f"Error in SMTP connection: {e}"
        utils_logger.debug(error_msg)
        return False, error_msg

    return True, "Email sent successfully."


def _check_parameter_types(mail_username, mail_password, mail_host, mail_port, mail_use_tls):
    
    # Data type validation
    if not isinstance(mail_username, str):
        return False, "mail_username must be a string"
    if not isinstance(mail_password, str):
        return False, "mail_password must be a string."
    if not isinstance(mail_host, str):
        return False, "mail_host must be a string."
    if not isinstance(mail_port, int):
        return False, "mail_port must be an integer."
    if not isinstance(mail_use_tls, bool):
        return False, "mail_use_tls must be a boolean."
    
    return True , ""


""" ********************************************** Main Functions ********************************************** """


def cutil_email_init(mail_username, mail_password, mail_host, mail_port, mail_use_tls):
    """
    Setting up email initialization.

    Args:
        mail_username (str): Sender's email address (used to log in and as the 'From' address).
        mail_password (str): Password or app-specific token for the sender's email account.
        mail_host (str): SMTP server address (e.g., "smtp@gmail.com").
        mail_port (int): SMTP server port (typically 587 for TLS, 465 for SSL).
        mail_use_tls (bool): Whether to use TLS encryption (True for port 587 with STARTTLS).

     Returns:
        tuple: (bool, MIMEMultipart or str) – success status and message or error string.
    """

    utils_logger.debug(f"cutil_email_init request : mail_username, mail_password, mail_host, mail_port, mail_use_tls "
                       f"{mail_username, mail_password ,mail_host, mail_port, mail_use_tls}")

    # Data type validation
    ret, msg = _check_parameter_types(mail_username, mail_password, mail_host, mail_port, mail_use_tls)
    if not ret:
        return ret, msg
    
    CutilSettings.mail_username = mail_username
    CutilSettings.mail_password = mail_password
    CutilSettings.mail_host = mail_host
    CutilSettings.mail_port = mail_port
    CutilSettings.mail_use_tls = mail_use_tls

    return True ,"Initialization Complete"


def cutil_send_email(mail_subject, mail_body, mail_tolist, attachments=None):
    """
    Creates an email message with optional attachments.

    Args:
        mail_tolist (list): Recipients list.
        mail_subject (str): Subject of the email.
        mail_body (str): HTML body of the email.
        attachments (list, optional): List of file paths to attach.

    Returns:
        tuple: (bool, MIMEMultipart or str) – success status and message or error string.
    """
    utils_logger.debug(
        f"cutil_send_email, mail_subject={mail_subject}, mail_tolist={mail_tolist}, attachments={attachments}")

    # Validate mail info
    ret, msg = _validate_mail_info(mail_tolist, attachments)
    if not ret:
        return ret, msg

    # Create a MIMEMultipart message
    msg = MIMEMultipart()
    msg['From'] = CutilSettings.mail_username
    msg['To'] = ', '.join(mail_tolist)
    msg['Subject'] = mail_subject

    # Attach the HTML body
    msg.attach(MIMEText(mail_body, 'html'))

    # Attach files in the msg
    if attachments:
        ret,  msg = _msg_append_attachments(msg, attachments)
        if not ret:
            utils_logger.debug(f"Invalid Attachments, some of files may not be present !")
            return False, 'Invalid Attachments, some of files may not be present!'

    # Sending email
    ret , msg = _send_email(mail_tolist, msg)
    return ret, msg 


