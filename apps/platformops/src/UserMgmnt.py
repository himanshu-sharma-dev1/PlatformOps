''''*******************************************************************************************************************
* Copyright         : PlatformOps
* File Name         : UserMgmnt.py
* Description       : Functions related to  User Mgmt
*
* Revision History  :
* Date				Author    		        Comments
* ---------------------------------------------------------------------------------------------------------------------
* 04-June-24 		Sumit Das 		            Updated.
*********************************************************************************************************************'''

import os
import requests
from pathlib import Path
import json
from django.contrib.auth.models import User
from django.contrib.auth.models import Group
from django.core.validators import EmailValidator
from django.core.exceptions import ValidationError

from CommonUtils.license.ValidationLicense import cutil_validate_license
from CommonUtils.timer.TimerMgr import cutil_timer_get_app_curr_time

try:
    from cPlatformIO.src import ReportMgmt
except ImportError:
    ReportMgmt = None
from cPlatformIO.src.PlatformSetting import PlatformSettings
from cPlatformIO.models import UserInfo, InviteToken,UserInfo
from cPlatform.AppLogging import app_logger
from cPlatformIO.src.AppConfig import app_route_service,app_get_config_info
from django.template.loader import get_template
from CommonUtils.com.EmailMgr import cutil_send_email, cutil_email_init

from datetime import date
import uuid
# Initializing Global variables
MAX_USERS = 9000
USER_BASE_IDX = 10000


# -----------------------------------------Utility Function------------------------------------------------------------

def _get_mapped_user_id(user_idx):
    user_id = 'UR' + str(USER_BASE_IDX + user_idx)
    app_logger.debug(f"_get_mapped_user_id: args-> user_idx={user_idx}, return-> user_id={user_id}")
    return user_id


def _create_user_instance(user_role, user_email, password):

    if user_role == 'System_Admin':
        # Creating SuperUser
        user = User.objects.create_superuser(username=user_email, password=password, email=user_email)
        my_group = Group.objects.get(name='Admin')
    elif user_role == 'Operational' or user_role == 'Management':
        # Creating regular user
        user = User.objects.create_user(username=user_email, password=password, email=user_email)
        my_group = Group.objects.get(name='PrimaryUsers')
    else:
        return 'Failure, Invalid Role Provided.'

    # Add user to the group
    my_group.user_set.add(user)
    return


def _create_userinfo_instance(user_name, user_email, user_role, user_number, status='active'):
    sys_time = cutil_timer_get_app_curr_time()
    user_ins = UserInfo.objects.create(user_name=user_name, user_email=user_email, user_role=user_role,
                                       created_date=sys_time.strftime('%Y-%m-%d'), user_number=user_number, status=status,)

    user_id = _get_mapped_user_id(user_ins.user_idx)
    user_ins.user_id = user_id
    user_ins.save()
    return user_ins


def _update_user(user_name, user_email, password, user_number, user_role):
    user_ins = UserInfo.objects.get(user_email=user_email)

    # Update System's User Table
    user_instance = User.objects.get(username=user_ins.user_email)
    user_instance.username = user_email
    if password!="":
        user_instance.set_password(password)
    user_instance.save()

    # Update User Info Model
    user_ins.user_name = user_name
    user_ins.user_email = user_email
    user_ins.user_number = user_number
    user_ins.user_role = user_role
    user_ins.save()

    return user_ins


def _validate_email(email):
    validator = EmailValidator()
    try:
        validator(email)
        return True
    except ValidationError:
        return False


def _validate_phone_number(user_number):
    if not user_number:
        return True
    return user_number.isdigit() and len(user_number) >= 10


def _validate_user_request(user_email, user_number):

    if not _validate_email(user_email):
        return False, 'Failure, Invalid email format.'

    if not _validate_phone_number(user_number):
        return False, "Failure, Invalid phone number format."

    return True, f"User Request Validated Successfully"


# -----------------------------------------User Config Function------------------------------------------------------


def user_get_instance__mail(user_email):
    if UserInfo.objects.filter(user_email=user_email).exists():
        return UserInfo.objects.get(user_email=user_email)

    return None


def user_get_info(user_email=None):
    if user_email is None:
        users = UserInfo.objects.all()
    else:
        users = UserInfo.objects.filter(user_email=user_email)

    user_info_list = []

    for user in users:
        try:
            user_ins = User.objects.get(username=user.user_email)
            last_login = user_ins.last_login.strftime("%d-%b-%y %H:%M") if user_ins.last_login else '—'
            last_login_ts = int(user_ins.last_login.timestamp()) if user_ins.last_login else 0
        except User.DoesNotExist:
            last_login = '—'
            last_login_ts = '—'
        print(f"{'-' * 20} user_ins: {user.user_email}")
        user_number = user.user_number if user.user_number else ''

        # Fetch invite token for pending users
        invite_token = ''
        if user.status == 'pending':
            try:
                invite = InviteToken.objects.filter(user_email=user.user_email,is_used=False,is_revoked=False).latest('created_at')
                invite_token = str(invite.token)
            except InviteToken.DoesNotExist:
                invite_token = ''

        user_info = {"user_id": user.user_id, "user_name": user.user_name, "user_email": user.user_email,
                     "password": user.user_email, "user_role": user.user_role, "user_number": user_number,
                     "created_date": user.created_date.strftime('%d-%b-%y'), "login_count": user.login_count,
                     "last_login": last_login, "last_login_ts": last_login_ts, "status": user.status,
                     "invite_token": invite_token,
                     }
        user_info_list.append(user_info)

    return user_info_list


def user_update_session_info(user_id, session_info):
    app_logger.debug(f"user_update_session_info, user_id=={user_id}, session_info={session_info}")
    if UserInfo.objects.filter(user_id=user_id).exists():
        user_ins = UserInfo.objects.get(user_id=user_id)
        user_ins.session_info = session_info
        user_ins.save()
    return

def user_update_last_visited(user_email, snapshot):
    app_logger.debug(f"user_update_last_visited, user_email={user_email}, snapshot={snapshot}")
    try:
        user_ins = UserInfo.objects.get(user_email=user_email)
        current_session = user_ins.session_info or {}
        current_session['last_visited'] = snapshot
        user_ins.session_info = current_session
        user_ins.save(update_fields=['session_info'])
    except UserInfo.DoesNotExist:
        app_logger.warning(f"user_update_last_visited: UserInfo not found for {user_email}")


def user_get_session_info(request):
    user_ins = user_get_instance__mail(request.user)
    session_info = user_ins.session_info
    return session_info

def get_session_info(user):
    user_ins = user_get_instance__mail(user)
    session_info = user_ins.session_info
    return session_info

def update_session_info(user, info):
    user_ins = user_get_instance__mail(user)
    session_info = user_ins.session_info
    session_info["last_visited"] = {
        "cluster_name": info.get("cluster_name"),
        "node_name": info.get("node_name"),
        "service_name": info.get("service_name"),
    }
    user_ins.session_info = session_info
    user_ins.save(update_fields=["session_info"])

def user_login_count_increment(user_mail):
    if UserInfo.objects.filter(user_email=user_mail).exists():
        user_ins = UserInfo.objects.filter(user_email=user_mail).first()
        if user_ins.login_count is None:
            user_ins.login_count = 0
        user_ins.login_count = user_ins.login_count + 1
        user_ins.save()

    return f'User Login Count Incremented, UserName:{user_mail}'


def user_license_validated(user_name):
    config_path = str(Path(__file__).resolve().parents[3] / 'config')
    ret = cutil_validate_license(config_path)
    user = User.objects.filter(username=user_name).first()
    if user.is_staff:
        return True
    else:
        return ret


def user_check_self_create(user_name):
    # Check if user already exists in UserInfo model
    user = User.objects.filter(username=user_name).first()
    if user and user.is_staff and not UserInfo.objects.filter(user_email=user_name).exists():
        # Add user to the group
        my_group, _ = Group.objects.get_or_create(name='Admin')
        my_group.user_set.add(user)

        # Create UserInfo instance
        _create_userinfo_instance(user.username, user.username, "System_Admin", None, status='active')

    return


# ---------------------------------------User API functions---------------------------------------------------------


def user_add_request(user_name, user_email, password, user_role, user_number):
    app_logger.debug(f"user_add_request:name, email, role, number={user_name, user_email, user_role, user_number}")

    user_number = None if user_number == '' else user_number
    ret, msg = _validate_user_request(user_email, user_number)
    if not ret:
        app_logger.info(msg)
        return msg

    # Validate that user email does not exist already
    if UserInfo.objects.filter(user_email=user_email).exists():
        return 'Failure, User Email already exists.'

    # Check if the maximum number of users has been reached
    if UserInfo.objects.all().count() >= MAX_USERS:
        return 'Failure, Maximum User Count Reached.'

    # Creating the user instance
    _create_user_instance(user_role, user_email, password)

    # Creating UserInfo instance
    user_ins = _create_userinfo_instance(user_name, user_email, user_role, user_number)

    return f"User {user_ins.user_name} added successfully .."


def user_edit_request(user_name, user_email, password, user_number, user_role):

    user_number = None if user_number == '' else user_number
    ret, msg = _validate_user_request(user_email, user_number)
    if not ret:
        app_logger.info(msg)
        return msg

    if not UserInfo.objects.filter(user_email=user_email).exists():
        return f"User {user_name} does not exist."

    user_ins = _update_user(user_name, user_email, password, user_number, user_role)
    return f"User = {user_ins.user_name} edited successfully !"


# def user_delete_request(user_id):
#
#     # Validate User ID Exists
#     if not UserInfo.objects.filter(user_id=user_id).exists():
#         return "User Does Not Exists"
#
#     # Validate No Mapped Report with this User
#     user_instance = UserInfo.objects.get(user_id=user_id)
#     if ReportMgmt.report_check_exists(user_instance):
#         return "Cannot delete, User is in use of Report"
#
#     # Get and Delete Instance
#     user_name = user_instance.user_name
#     user_ins = User.objects.get(username=user_instance.user_email)
#     user_ins.delete()
#     user_instance.delete()
#     return f'User "{user_name}" Deleted Successfully...'


def service_user_delete(user_email):
    app_logger.debug(f"service_user_delete----user_email: {user_email}")
    user_ins = user_get_instance__mail(user_email)
    app_service_dict = app_get_config_info()
    app_logger.debug(f"\n\napp_service_dict: {json.dumps(app_service_dict, indent=4, default=str)}\n")

    for app in app_service_dict:
        app_name = app['app_name']

        for mapped_service in app.get('mapped_services', []):

            for service, service_key in mapped_service.items():
                service_name = service.split('_SERV')[0]

                ret, host, port = app_route_service(app_name, service_key, service_name)
                app_logger.debug(f"\napp: {app_name} | service_name: {service_name} | service_key: {service_key} | ret, host, port: {ret, host, port}")

                if ret:
                    ser_url = f'http://{host}:{port}/cPlatformApp/APIv1/User/Delete/'
                    payload = {'username': user_ins.user_email}
                    resp = requests.post(url=ser_url, json=payload)
                    app_logger.debug(f"service_user_delete response for {app_name}/{service}: {resp}")

#invite user
def service_user_invite(name, user_email, phone, role, permissions, invited_by):
    app_logger.debug(f"fxn : service_user_invite : {name, user_email, phone, role, permissions, invited_by} ")
    invite = InviteToken.objects.create(
        user_name=name,
        user_email=user_email,
        user_number=phone or '',
        user_role=role,
        permissions=permissions,
        invited_by=invited_by,
    )

    # Create UserInfo record with pending status
    UserInfo.objects.create(
        user_id=str(uuid.uuid4())[:8],
        user_email=user_email,
        user_name=name,
        user_role=role,
        user_number=phone or '',
        created_date=date.today(),
        status='pending',
    )

    # Build the link
    base_url = str(getattr(PlatformSettings, "cplatform_url", "") or "").rstrip("/")
    if not base_url or "iktaratech.com" in base_url:
        base_url = "http://localhost:9020"
    invite_link = f"{base_url}/invite/accept/{invite.token}/"


    # Send email
    mail_subject = f"You're invited to join PlatformOps"
    mail_body = get_template('PlatformIO/email_invite.html').render({
        "invite_link": invite_link,
        "user_name": name,
        "invited_by": invited_by,
        "role": role,
        "expires_in": "30 days",
    })
    mail_config = PlatformSettings.get_config().mail
    ret, msg = cutil_email_init(
        mail_config['mail_username'],
        mail_config['mail_password'],
        mail_config['mail_host'],
        mail_config['mail_port'],
        mail_config['mail_use_tls'],
    )
    print(f"cutil_email_init result: ret={ret}, msg={msg}")
    print(f"\n\nSending mail...")
    ret, msg = cutil_send_email(mail_subject, mail_body, [user_email])
    print(f"cutil_send_email result: ret={ret}, msg={msg}")

    return invite

def service_user_resend_invite_bulk(emails, invited_by):
    sent_count = 0
    skipped_count = 0

    # Email configs (init once)
    mail_config = PlatformSettings.get_config().mail
    cutil_email_init(
        mail_config['mail_username'],
        mail_config['mail_password'],
        mail_config['mail_host'],
        mail_config['mail_port'],
        mail_config['mail_use_tls'],
    )

    for user_email in emails:
        user_email = user_email.strip()
        # Get user info
        user = UserInfo.objects.get(user_email=user_email)
        # Only process pending users
        if user.status != 'pending':
            skipped_count += 1
            continue

        # Revoke all existing unused, unrevoked tokens for this email
        InviteToken.objects.filter(
            user_email=user_email,
            is_used=False,
            is_revoked=False
        ).update(is_revoked=True)

        # Create a fresh token
        invite = InviteToken.objects.create(
            user_name   = user.user_name,
            user_email  = user_email,
            user_number = user.user_number or '',
            user_role   = user.user_role,
            invited_by  = invited_by,
        )

        # Reset created_date so expiry bar restarts from today
        user.created_date = date.today()
        user.save()
        # Build link and send email
        base_url = str(getattr(PlatformSettings, "cplatform_url", "") or "").rstrip("/")
        if not base_url or "iktaratech.com" in base_url:
            base_url = "http://localhost:9020"
        invite_link = f"{base_url}/invite/accept/{invite.token}/"
        mail_body = get_template('PlatformIO/email_invite.html').render({
            "invite_link": invite_link,
            "user_name":   user.user_name,
            "invited_by":  invited_by,
            "role":        user.user_role,
            "expires_in":  "30 days",
        })
        ret, msg = cutil_send_email("You're invited to join PlatformOps", mail_body, [user_email])
        if ret:
            sent_count += 1
    return sent_count, skipped_count

def service_revoke_and_delete_pending(user_email, invited_by):
    app_logger.debug(f"fxn: service_revoke_and_delete_pending: {user_email}")

    # Send revoke email first
    try:
        mail_body = get_template('PlatformIO/email_invite_revoked.html').render({
            "user_email": user_email,
            "revoked_by": invited_by,
        })
        mail_config = PlatformSettings.get_config().mail
        cutil_email_init(
            mail_config['mail_username'], mail_config['mail_password'],
            mail_config['mail_host'], mail_config['mail_port'], mail_config['mail_use_tls'],
        )
        cutil_send_email("Your PlatformOps invitation has been revoked", mail_body, [user_email])
    except Exception as e:
        print(f"Email failed: {e}")

    # Delete InviteToken records
    InviteToken.objects.filter(user_email=user_email).delete()

    # Delete UserInfo
    UserInfo.objects.filter(user_email=user_email).delete()


#deleting active users
def user_delete_request(user_email, initiated_by):
    app_logger.debug(f"fxn: service_delete_active_user: {user_email, initiated_by}")

    # Validate No Mapped Report with this User
    user_instance = UserInfo.objects.get(user_email=user_email)
    if ReportMgmt and ReportMgmt.report_check_exists(user_instance):
        return "Cannot delete, User is in use of Report"

    # Delete UserInfo -Validate User ID Exists
    if not UserInfo.objects.filter(user_email=user_email).exists():
        return "User Does Not Exists"
    else:
        UserInfo.objects.filter(user_email=user_email).delete()

    # Delete Django User
    User.objects.filter(username=user_email).delete()

    try:
        mail_body = get_template('PlatformIO/email_account_deleted.html').render({
            "user_email": user_email,
            "deleted_by": initiated_by,
        })
        mail_config = PlatformSettings.get_config().mail
        cutil_email_init(
            mail_config['mail_username'], mail_config['mail_password'],
            mail_config['mail_host'], mail_config['mail_port'], mail_config['mail_use_tls'],
        )
        cutil_send_email("Your PlatformOps account has been deleted", mail_body, [user_email])
        print("email sent!")
    except Exception as e:
        print(f"Email failed: {e}")

    # Delete InviteToken records
    InviteToken.objects.filter(user_email=user_email).delete()
