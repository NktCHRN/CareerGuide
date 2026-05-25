"use server";

import { redirect } from "next/navigation";

import { ApiError, friendlyMessage } from "@/lib/api/errors";
import {
  login,
  register,
  requestPasswordReset,
  resetPassword,
} from "@/lib/api/users";
import { clearAuthCookies, setAuthCookies } from "@/lib/auth/cookies";

/** Guard against open redirects: only allow same-site absolute paths. */
function safeNext(next: string): string {
  if (next.startsWith("/") && !next.startsWith("//")) return next;
  return "/recommendations";
}

const EMAIL_RE = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

// --------------------------------------------------------------------------- //
//  Login
// --------------------------------------------------------------------------- //
export interface LoginState {
  error?: string;
}

export async function loginAction(
  _prev: LoginState,
  formData: FormData,
): Promise<LoginState> {
  const email = String(formData.get("email") ?? "").trim();
  const password = String(formData.get("password") ?? "");
  const next = safeNext(String(formData.get("next") ?? ""));

  if (!email || !password) {
    return { error: "Please enter your email and password." };
  }

  try {
    const tokens = await login({ email, password });
    await setAuthCookies(tokens);
  } catch (err) {
    return { error: friendlyMessage(err, "Unable to sign in. Please try again.") };
  }
  redirect(next);
}

// --------------------------------------------------------------------------- //
//  Register
// --------------------------------------------------------------------------- //
export interface RegisterState {
  error?: string;
  ok?: boolean;
  email?: string;
  verificationToken?: string | null;
}

export async function registerAction(
  _prev: RegisterState,
  formData: FormData,
): Promise<RegisterState> {
  const email = String(formData.get("email") ?? "").trim();
  const password = String(formData.get("password") ?? "");
  const confirm = String(formData.get("confirm") ?? "");
  const name = String(formData.get("name") ?? "").trim();

  if (!EMAIL_RE.test(email)) return { error: "Please enter a valid email address." };
  if (password.length < 8) {
    return { error: "Your password must be at least 8 characters long." };
  }
  if (password !== confirm) return { error: "The passwords do not match." };

  try {
    const res = await register({
      email,
      password,
      profile: name ? { name } : null,
    });
    await setAuthCookies(res);
    return { ok: true, email, verificationToken: res.email_verification_token };
  } catch (err) {
    if (err instanceof ApiError && err.status === 409) {
      return { error: "This email is already registered. Try signing in instead." };
    }
    return { error: friendlyMessage(err, "Unable to create your account.") };
  }
}

// --------------------------------------------------------------------------- //
//  Logout
// --------------------------------------------------------------------------- //
export async function logoutAction(): Promise<void> {
  await clearAuthCookies();
  redirect("/login");
}

// --------------------------------------------------------------------------- //
//  Password reset
// --------------------------------------------------------------------------- //
export interface ResetRequestState {
  error?: string;
  ok?: boolean;
  devToken?: string | null;
}

export async function requestResetAction(
  _prev: ResetRequestState,
  formData: FormData,
): Promise<ResetRequestState> {
  const email = String(formData.get("email") ?? "").trim();
  if (!EMAIL_RE.test(email)) {
    return { error: "Please enter a valid email address." };
  }
  try {
    const res = await requestPasswordReset(email);
    return { ok: true, devToken: res.dev_token };
  } catch (err) {
    return { error: friendlyMessage(err) };
  }
}

export interface ResetPasswordState {
  error?: string;
  ok?: boolean;
}

export async function resetPasswordAction(
  _prev: ResetPasswordState,
  formData: FormData,
): Promise<ResetPasswordState> {
  const token = String(formData.get("token") ?? "").trim();
  const password = String(formData.get("password") ?? "");
  const confirm = String(formData.get("confirm") ?? "");

  if (!token) return { error: "The reset link is missing its token." };
  if (password.length < 8) {
    return { error: "Your new password must be at least 8 characters long." };
  }
  if (password !== confirm) return { error: "The passwords do not match." };

  try {
    await resetPassword({ token, new_password: password });
    return { ok: true };
  } catch (err) {
    return {
      error: friendlyMessage(err, "This reset link is invalid or has expired."),
    };
  }
}
