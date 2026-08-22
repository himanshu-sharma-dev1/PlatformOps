// @ts-nocheck
import { useState } from "react";
export function useAuthState() {
  const [authUser, setAuthUser] = useState(null as any);
  const [authReady, setAuthReady] = useState(false as any);
  const [loginForm, setLoginForm] = useState({ email: "admin", password: "admin" } as any);
  const [loginError, setLoginError] = useState("" as any);
  const [loginBusy, setLoginBusy] = useState(false as any);
  const [platformUsers, setPlatformUsers] = useState([] as any);
  const [usersLoading, setUsersLoading] = useState(false as any);
  const [usersError, setUsersError] = useState("" as any);
  const [usersTab, setUsersTab] = useState("active" as any);
  const [inviteForm, setInviteForm] = useState({ user_name: "", user_email: "", user_role: "Operational", user_number: "", permissions: [] } as any);
  const [userForm, setUserForm] = useState({ user_name: "", user_email: "", user_role: "Operational", user_number: "", password: "", permissions: [] } as any);
  const [inviteAccept, setInviteAccept] = useState(null as any);
  return {
    authUser, setAuthUser,
    authReady, setAuthReady,
    loginForm, setLoginForm,
    loginError, setLoginError,
    loginBusy, setLoginBusy,
    platformUsers, setPlatformUsers,
    usersLoading, setUsersLoading,
    usersError, setUsersError,
    usersTab, setUsersTab,
    inviteForm, setInviteForm,
    userForm, setUserForm,
    inviteAccept, setInviteAccept,
  };
}
