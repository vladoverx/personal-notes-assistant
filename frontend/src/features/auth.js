import * as api from '../services/api.js';
import { ENABLE_SIGNUP_UI, SIGNUP_CONTACT_EMAIL } from '../config.js';

let callbacks = { onAuthSuccess: null, onSignOut: null };
let currentUser = null;

export function initAuth({ onAuthSuccess, onSignOut }) {
  callbacks.onAuthSuccess = typeof onAuthSuccess === 'function' ? onAuthSuccess : () => {};
  callbacks.onSignOut = typeof onSignOut === 'function' ? onSignOut : () => {};

  const showSignupBtn = document.getElementById('show-signup');
  const showSigninBtn = document.getElementById('show-signin');
  const signinForm = document.getElementById('signin-form');
  const signupForm = document.getElementById('signup-form');
  const signoutBtn = document.getElementById('signout-btn');
  const welcomeSubtitle = document.querySelector('.welcome-subtitle');
  const segmented = document.querySelector('.segmented-control');
  const authCardHeader = document.querySelector('.auth-card-header');

  // segmented control behavior
  if (ENABLE_SIGNUP_UI) {
    showSignupBtn?.addEventListener('click', () => toggleAuthForms('signup'));
  } else {
    // Hide signup tab and form, update subtitle with contact
    showSignupBtn?.classList.add('hidden');
    signupForm?.classList.add('hidden');
    segmented?.classList.add('single');
    authCardHeader?.classList.add('centered');
    const contact = SIGNUP_CONTACT_EMAIL || '';
    if (welcomeSubtitle) {
      welcomeSubtitle.textContent = contact
        ? `Signups are closed. Email ${contact} to request access.`
        : 'Signups are closed. Please contact the administrator to request access.';
      welcomeSubtitle.classList.add('centered');
    }
  }
  showSigninBtn?.addEventListener('click', () => toggleAuthForms('signin'));

  signinForm?.addEventListener('submit', handleSignIn);
  signupForm?.addEventListener('submit', handleSignUp);
  signoutBtn?.addEventListener('click', handleSignOut);
}

export async function validateToken() {
  try {
    const user = await api.validateToken();
    currentUser = user;
    callbacks.onAuthSuccess?.(user);
    return user;
  } catch {
    // If invalid, ensure signed out UI
    api.clearSession();
    currentUser = null;
    callbacks.onSignOut?.();
    throw new Error('Invalid token');
  }
}

async function handleSignIn(event) {
  event.preventDefault();
  const email = document.getElementById('signin-email').value;
  const password = document.getElementById('signin-password').value;
  try {
    const data = await api.signIn(email, password);
    api.setSession(data);
    currentUser = data.user;
    callbacks.onAuthSuccess?.(data.user);
  } catch (err) {
    // Show friendly rate limit message if 429
    if (err && err.status === 429) {
      const waitSecs = Number.isFinite(err?.retryAfter) ? err.retryAfter : null;
      const msg = waitSecs
        ? `Too many sign in attempts. Please wait ${waitSecs} seconds and try again.`
        : 'Too many sign in attempts. Please try again shortly.';
      alert(msg);
      return;
    }
    alert(`Sign in failed: ${err?.message || 'Invalid credentials'}`);
  }
}

async function handleSignUp(event) {
  event.preventDefault();
  if (!ENABLE_SIGNUP_UI) {
    const contact = SIGNUP_CONTACT_EMAIL || '';
    alert(contact
      ? `Signups are currently closed. Please email ${contact} to request an invite.`
      : 'Signups are currently closed. Please contact the support to request an invite.');
    return;
  }
  const email = document.getElementById('signup-email').value;
  const password = document.getElementById('signup-password').value;
  const confirmPassword = document.getElementById('signup-confirm-password').value;
  if (password !== confirmPassword) { alert('Passwords do not match'); return; }
  if (password.length < 8) { alert('Password must be at least 8 characters long'); return; }
  try {
    const data = await api.signUp(email, password);
    if (data && data.access_token) {
      api.setSession(data);
      currentUser = data.user;
      callbacks.onAuthSuccess?.(data.user);
    } else {
      alert('Account created successfully! Please sign in.');
      toggleAuthForms('signin');
    }
  } catch (err) {
    if (err && err.status === 429) {
      const waitSecs = Number.isFinite(err?.retryAfter) ? err.retryAfter : null;
      const msg = waitSecs
        ? `Too many sign up attempts. Please wait ${waitSecs} seconds and try again.`
        : 'Too many sign up attempts. Please try again shortly.';
      alert(msg);
      return;
    }
    // Map backend invite-only error to friendly message
    const msg = String(err?.message || '').toLowerCase();
    if (
      msg.includes('signups are disabled') ||
      msg.includes('signup disabled') ||
      msg.includes('signups disabled')
    ) {
      const contact = SIGNUP_CONTACT_EMAIL || '';
      alert(contact
        ? `Signups are closed. Please email ${contact} to request an invite.`
        : 'Signups are closed. Please contact the support to request an invite.');
    } else {
      alert(`Sign up failed: ${err?.message || 'Please try again'}`);
    }
  }
}

async function handleSignOut() {
  try { await api.signOut(); } catch { /* ignore network errors on signout */ }
  api.clearSession();
  currentUser = null;
  callbacks.onSignOut?.();
}

function toggleAuthForms(form) {
  const signinForm = document.getElementById('signin-form');
  const signupForm = document.getElementById('signup-form');
  const showSigninBtn = document.getElementById('show-signin');
  const showSignupBtn = document.getElementById('show-signup');
  const signinTab = showSigninBtn; const signupTab = showSignupBtn;
  const showSignup = form === 'signup';
  signupForm.classList.toggle('hidden', !showSignup);
  signinForm.classList.toggle('hidden', showSignup);
  signupTab?.classList.toggle('active', showSignup);
  signinTab?.classList.toggle('active', !showSignup);
}


