''''*******************************************************************************************************************
* Copyright         : PlatformOps
* File Name         : decorators.py
* Description       : Common Utility Module supporting Authorization
*
* Revision History  :
* Date				Author    		        Comments
* ---------------------------------------------------------------------------------------------------------------------
* 15-June-23 		Yogita		            Created.
*
*********************************************************************************************************************'''

from django.shortcuts import redirect
from django.contrib import messages


def allowed_users(allowed_roles=[]):
    def decorator(view_func):
        def wrapper_func(request, *args, **kwargs):
            user_group_list = []
            group = None
            if request.user.groups.exists():
                group = request.user.groups.all()
                for user_group in range(len(group)):
                    user_group_list.append(group[user_group].name)
                print(f"user_group_list:{user_group_list}")
                if any(item in allowed_roles for item in user_group_list):
                    return view_func(request, *args, **kwargs)
                else:
                    messages.warning(request,'User not authorized')

                    return redirect('login')
            else:
                messages.warning(request,'User must belong to atleast one group')
                return redirect('login')
        return wrapper_func
    return decorator



def admin_only(view_func):
    def wrapper_function(request, *args, **kwargs):
        group=None
        user_group_list = []
        if request.user.groups.exists():
            group = request.user.groups.all()
            for user_group in range(len(group)):
                user_group_list.append(group[user_group].name)
            if 'Admin' in user_group_list:
                return view_func(request, *args, **kwargs)
            else:
                messages.warning(request, 'User must be admin')
                return redirect('login')
        else:
            messages.warning(request, 'User must belong to a Group ')
            return redirect('login')
    return wrapper_function
