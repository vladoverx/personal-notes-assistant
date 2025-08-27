// Application configuration (runtime overridable via window.__APP_CONFIG__)
const runtimeConfig = (typeof window !== 'undefined' && window.__APP_CONFIG__) || {};
export const API_BASE_URL = runtimeConfig.API_BASE_URL || 'http://localhost:8000/api/v1';

// Auth UI configuration
// If set to false, the Sign Up tab/form is hidden and a friendly message is shown.
export const ENABLE_SIGNUP_UI = runtimeConfig.ENABLE_SIGNUP_UI || false;

// Contact email to display when signups are closed
export const SIGNUP_CONTACT_EMAIL = runtimeConfig.SIGNUP_CONTACT_EMAIL || 'support@notekin.online';


