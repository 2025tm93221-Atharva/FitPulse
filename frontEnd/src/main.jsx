import React, { useEffect, useMemo, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { QRCodeSVG } from 'qrcode.react';
import {
  Activity,
  Bell,
  CalendarDays,
  CheckCircle2,
  CircleHelp,
  CreditCard,
  Dumbbell,
  KeyRound,
  LoaderCircle,
  LogOut,
  Mail,
  RefreshCw,
  Save,
  Send,
  Settings,
  ShieldCheck,
  UserRound,
  XCircle,
} from 'lucide-react';
import './styles.css';

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000';

async function apiFetch(path, options = {}, accessToken = null) {
  const headers = new Headers(options.headers || {});
  if (options.body && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json');
  if (accessToken) headers.set('Authorization', `Bearer ${accessToken}`);

  let response;
  try {
    response = await fetch(`${API_BASE}${path}`, { ...options, headers });
  } catch {
    throw new Error('API not reachable. Check the network connection and API health endpoint.');
  }

  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const message = Array.isArray(data.detail)
      ? data.detail.map((item) => item.msg).join(', ')
      : data.detail || `Request failed (${response.status})`;
    throw new Error(message);
  }
  return data;
}

function localDateString(date = new Date()) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

function humanDate(value) {
  if (!value) return '—';
  const parsed = new Date(`${value.slice(0, 10)}T12:00:00`);
  return parsed.toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' });
}

function formatTimestamp(value) {
  if (!value) return 'No visits recorded yet';
  return new Date(value).toLocaleString(undefined, {
    day: 'numeric', month: 'short', hour: 'numeric', minute: '2-digit',
  });
}

function membershipDisplayStatus(membership, today) {
  if (membership.status === 'active' && membership.expiry_date < today) return 'Expired';
  if (membership.status === 'active' && membership.start_date > today) return 'Scheduled';
  return membership.status.charAt(0).toUpperCase() + membership.status.slice(1);
}

function App() {
  const initialResetToken = new URLSearchParams(window.location.search).get('reset_token') || '';
  const [mode, setMode] = useState(initialResetToken ? 'reset' : 'login');
  const [form, setForm] = useState({ email: '', password: '', full_name: '' });
  const [resetToken, setResetToken] = useState(initialResetToken);
  const [newPassword, setNewPassword] = useState('');
  const [profileName, setProfileName] = useState('');
  const [privacy, setPrivacy] = useState({ analytics_consent: false, marketing_consent: false });
  const [notifications, setNotifications] = useState([]);
  const [supportTickets, setSupportTickets] = useState([]);
  const [supportForm, setSupportForm] = useState({ category: 'access', subject: '', message: '' });
  const [session, setSession] = useState(null);
  const [memberships, setMemberships] = useState([]);
  const [checkIns, setCheckIns] = useState([]);
  const [pass, setPass] = useState(null);
  const [busy, setBusy] = useState(false);
  const [passBusy, setPassBusy] = useState(false);
  const [, setExpiryTick] = useState(0);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [apiStatus, setApiStatus] = useState({ state: 'loading', message: 'Connecting to API…' });

  const today = localDateString();
  const currentMembership = useMemo(
    () => memberships.find((m) => m.status === 'active' && m.start_date <= today && m.expiry_date >= today) || null,
    [memberships, today],
  );
  const visitsThisMonth = useMemo(() => {
    const now = new Date();
    return checkIns.filter((item) => {
      const timestamp = new Date(item.checked_in_at);
      return timestamp.getFullYear() === now.getFullYear() && timestamp.getMonth() === now.getMonth();
    }).length;
  }, [checkIns]);
  const latestCheckIn = checkIns[0] || null;
  const passExpired = pass ? Date.now() >= Date.parse(pass.expires_at) : false;
  const unreadNotifications = notifications.filter((item) => !item.is_read).length;

  useEffect(() => {
    if (!pass) return undefined;
    const remainingMs = Date.parse(pass.expires_at) - Date.now();
    const timer = window.setTimeout(() => setExpiryTick((value) => value + 1), Math.max(remainingMs, 0) + 50);
    return () => window.clearTimeout(timer);
  }, [pass]);

  async function checkApi() {
    setApiStatus({ state: 'loading', message: 'Connecting to API…' });
    try {
      const response = await apiFetch('/api/health');
      setApiStatus({ state: 'ok', message: `${response.status} · ${response.service}` });
    } catch {
      setApiStatus({ state: 'error', message: 'API not reachable. Start FastAPI on port 8000.' });
    }
  }

  useEffect(() => { checkApi(); }, []);

  async function loadDashboard(accessToken) {
    const [membershipData, checkInData, notificationData, privacyData, ticketData, profileData] = await Promise.all([
      apiFetch('/api/memberships/me', {}, accessToken),
      apiFetch('/api/check-ins/me', {}, accessToken),
      apiFetch('/api/notifications/me', {}, accessToken),
      apiFetch('/api/privacy/preferences', {}, accessToken),
      apiFetch('/api/support/tickets/me', {}, accessToken),
      apiFetch('/api/users/me', {}, accessToken),
    ]);
    setMemberships(membershipData);
    setCheckIns(checkInData);
    setNotifications(notificationData);
    setPrivacy({ analytics_consent: privacyData.analytics_consent, marketing_consent: privacyData.marketing_consent });
    setSupportTickets(ticketData);
    setProfileName(profileData.full_name);
  }

  async function submitAuth(event) {
    event.preventDefault();
    setBusy(true);
    setError('');
    setNotice('');
    try {
      if (mode === 'register') {
        await apiFetch('/api/auth/register', {
          method: 'POST',
          body: JSON.stringify({ email: form.email, full_name: form.full_name, password: form.password }),
        });
        setMode('login');
        setForm((previous) => ({ ...previous, password: '' }));
        setNotice('Account created. Sign in, then contact your club to have a membership assigned.');
      } else if (mode === 'forgot') {
        const result = await apiFetch('/api/auth/password-reset/request', {
          method: 'POST', body: JSON.stringify({ email: form.email }),
        });
        setNotice(result.message || 'If an active account exists for this email, password-reset instructions will be sent.');
        if (result.debug_reset_token) {
          setResetToken(result.debug_reset_token);
          setMode('reset');
          setNotice('Development reset token created. Choose a new password to finish account recovery.');
        }
      } else if (mode === 'reset') {
        await apiFetch('/api/auth/password-reset/confirm', {
          method: 'POST', body: JSON.stringify({ token: resetToken, new_password: newPassword }),
        });
        window.history.replaceState({}, document.title, window.location.pathname);
        setMode('login');
        setResetToken('');
        setNewPassword('');
        setForm((previous) => ({ ...previous, password: '' }));
        setNotice('Password reset complete. Sign in with your new password. Existing sessions have been revoked.');
      } else {
        const result = await apiFetch('/api/auth/login', {
          method: 'POST',
          body: JSON.stringify({ email: form.email, password: form.password }),
        });
        await loadDashboard(result.access_token);
        // Keep the bearer token in memory only; never persist it to localStorage.
        setSession({ accessToken: result.access_token, user: result.user });
        setPass(null);
        setForm((previous) => ({ ...previous, password: '' }));
      }
    } catch (requestError) {
      setError(requestError.message || 'Request failed. Please try again.');
    } finally {
      setBusy(false);
    }
  }

  async function saveProfile(event) {
    event.preventDefault();
    if (!session) return;
    setBusy(true); setError(''); setNotice('');
    try {
      const updated = await apiFetch('/api/users/me', {
        method: 'PATCH', body: JSON.stringify({ full_name: profileName }),
      }, session.accessToken);
      setSession((previous) => ({ ...previous, user: updated }));
      setProfileName(updated.full_name);
      setNotice('Profile details saved.');
    } catch (requestError) {
      setError(requestError.message || 'Could not update profile.');
    } finally { setBusy(false); }
  }

  async function savePrivacy(event) {
    event.preventDefault();
    if (!session) return;
    setBusy(true); setError(''); setNotice('');
    try {
      const saved = await apiFetch('/api/privacy/preferences', {
        method: 'PATCH', body: JSON.stringify(privacy),
      }, session.accessToken);
      setPrivacy({ analytics_consent: saved.analytics_consent, marketing_consent: saved.marketing_consent });
      setNotice('Privacy preferences saved. Essential membership and security processing remains enabled.');
    } catch (requestError) {
      setError(requestError.message || 'Could not save privacy preferences.');
    } finally { setBusy(false); }
  }

  async function markNotificationRead(notificationId) {
    if (!session) return;
    try {
      const updated = await apiFetch(`/api/notifications/${notificationId}/read`, { method: 'PATCH' }, session.accessToken);
      setNotifications((previous) => previous.map((item) => item.id === updated.id ? updated : item));
    } catch (requestError) { setError(requestError.message || 'Could not update notification.'); }
  }

  async function markAllNotificationsRead() {
    if (!session) return;
    try {
      await apiFetch('/api/notifications/me/read-all', { method: 'POST' }, session.accessToken);
      setNotifications((previous) => previous.map((item) => ({ ...item, is_read: true })));
      setNotice('All notifications marked as read.');
    } catch (requestError) { setError(requestError.message || 'Could not update notifications.'); }
  }

  async function submitSupportTicket(event) {
    event.preventDefault();
    if (!session) return;
    setBusy(true); setError(''); setNotice('');
    try {
      const ticket = await apiFetch('/api/support/tickets', {
        method: 'POST', body: JSON.stringify(supportForm),
      }, session.accessToken);
      setSupportTickets((previous) => [ticket, ...previous]);
      setSupportForm({ category: 'access', subject: '', message: '' });
      const notificationData = await apiFetch('/api/notifications/me', {}, session.accessToken);
      setNotifications(notificationData);
      setNotice(`Support request #${ticket.id} submitted. Track updates in this dashboard.`);
    } catch (requestError) {
      setError(requestError.message || 'Could not submit your support request.');
    } finally { setBusy(false); }
  }

  async function generatePass() {
    if (!session) return;
    setPassBusy(true);
    setError('');
    setNotice('');
    try {
      const result = await apiFetch('/api/check-ins/qr-token', { method: 'POST' }, session.accessToken);
      setPass(result);
    } catch (requestError) {
      setPass(null);
      setError(requestError.message || 'Could not generate a gym pass.');
    } finally {
      setPassBusy(false);
    }
  }

  async function refreshActivity() {
    if (!session) return;
    setError('');
    try {
      await loadDashboard(session.accessToken);
      setNotice('Membership and check-in information refreshed.');
    } catch (requestError) {
      setError(requestError.message || 'Could not refresh account information.');
    }
  }

  function signOut() {
    setSession(null);
    setMemberships([]);
    setCheckIns([]);
    setNotifications([]);
    setSupportTickets([]);
    setPass(null);
    setError('');
    setNotice('You have signed out.');
  }

  function initials(user) {
    return (user?.full_name || user?.email || 'FM')
      .split(/[\s@.]+/)
      .filter(Boolean)
      .slice(0, 2)
      .map((part) => part[0].toUpperCase())
      .join('');
  }

  if (!session) {
    return (
      <div className="auth-shell">
        <div className="auth-brand"><Dumbbell size={22} /><span>FIT PULSE</span></div>
        <main className="auth-card">
          <p className="eyebrow">MEMBER ACCESS</p>
          <h1>{mode === 'login' ? 'Welcome back.' : mode === 'register' ? 'Join your club.' : mode === 'forgot' ? 'Recover your account.' : 'Choose a new password.'}</h1>
          <p className="auth-subtitle">
            {mode === 'login'
              ? 'Sign in to view your membership and secure digital pass.'
              : mode === 'register'
                ? 'Create your member account. Your club must assign a membership before gym entry is enabled.'
                : mode === 'forgot'
                  ? 'Enter the email associated with your account. We will provide reset instructions if an active account exists.'
                  : 'Use the secure reset link from your email to set a new password. Reset links expire and can only be used once.'}
          </p>

          {notice && <div className="notice-message"><CheckCircle2 size={16} />{notice}</div>}
          {error && <div className="error-message"><XCircle size={16} /><span>{error}</span></div>}

          <form className="auth-form" onSubmit={submitAuth}>
            {mode === 'register' && (
              <label>
                Full name
                <input
                  autoComplete="name"
                  required
                  minLength={1}
                  maxLength={120}
                  value={form.full_name}
                  onChange={(event) => setForm({ ...form, full_name: event.target.value })}
                  placeholder="Your name"
                />
              </label>
            )}
            {mode !== 'reset' && (
              <label>
                Email address
                <input
                  type="email"
                  autoComplete="email"
                  required
                  value={form.email}
                  onChange={(event) => setForm({ ...form, email: event.target.value })}
                  placeholder="you@example.com"
                />
              </label>
            )}
            {(mode === 'login' || mode === 'register') && (
              <label>
                Password {mode === 'register' && <span className="input-hint">12 characters minimum</span>}
                <input
                  type="password"
                  autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
                  required
                  minLength={mode === 'register' ? 12 : 1}
                  maxLength={128}
                  value={form.password}
                  onChange={(event) => setForm({ ...form, password: event.target.value })}
                  placeholder={mode === 'login' ? 'Your password' : 'Create a strong password'}
                />
              </label>
            )}
            {mode === 'reset' && (
              <>
                <label>
                  Password reset token
                  <input required minLength={20} value={resetToken} onChange={(event) => setResetToken(event.target.value)} placeholder="Paste token from reset email" />
                </label>
                <label>
                  New password <span className="input-hint">12 characters minimum</span>
                  <input type="password" autoComplete="new-password" required minLength={12} maxLength={128} value={newPassword} onChange={(event) => setNewPassword(event.target.value)} placeholder="Create a strong password" />
                </label>
              </>
            )}
            <button className="primary-button auth-submit" type="submit" disabled={busy}>
              {busy ? <LoaderCircle className="spin" size={16} /> : mode === 'login' || mode === 'reset' ? <KeyRound size={16} /> : mode === 'forgot' ? <Mail size={16} /> : <UserRound size={16} />}
              {busy ? 'Please wait…' : mode === 'login' ? 'Sign In' : mode === 'register' ? 'Create Account' : mode === 'forgot' ? 'Send Reset Instructions' : 'Reset Password'}
            </button>
          </form>

          {mode === 'login' && (
            <div className="auth-switch"><span>Forgot your password?</span>
              <button type="button" onClick={() => { setMode('forgot'); setError(''); setNotice(''); }}>Recover account</button>
            </div>
          )}
          <div className="auth-switch">
            <span>{mode === 'register' ? 'Already have an account?' : mode === 'login' ? 'New to your club?' : 'Return to sign in?'}</span>
            <button type="button" onClick={() => { setMode(mode === 'login' ? 'register' : 'login'); setError(''); setNotice(''); setNewPassword(''); }}>
              {mode === 'login' ? 'Create account' : 'Sign in'}
            </button>
          </div>
          <div className="api-health-inline">
            {apiStatus.state === 'ok' ? <CheckCircle2 size={14} /> : apiStatus.state === 'error' ? <XCircle size={14} /> : <LoaderCircle size={14} className="spin" />}
            <span>{apiStatus.message}</span>
            <button type="button" onClick={checkApi} aria-label="Test API connection"><RefreshCw size={13} /></button>
          </div>
        </main>
        <p className="auth-legal">Secure account access · Your pass is generated by the membership API.</p>
      </div>
    );
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand-mark"><Dumbbell size={20} /><span>FIT PULSE</span></div>
        <p className="nav-label">MEMBER SPACE</p>
        <a className="nav-item active" href="#overview"><Activity size={17} /> Overview</a>
        <a className="nav-item" href="#membership"><CreditCard size={17} /> Membership</a>
        <a className="nav-item" href="#activity"><CalendarDays size={17} /> Visit history</a>
        <a className="nav-item" href="#notifications"><Bell size={17} /> Notifications {unreadNotifications > 0 && <span className="nav-count">{unreadNotifications}</span>}</a>
        <a className="nav-item" href="#profile"><UserRound size={17} /> Profile</a>
        <a className="nav-item" href="#privacy"><Settings size={17} /> Privacy</a>
        <a className="nav-item" href="#support"><CircleHelp size={17} /> Help & support</a>
        <div className="sidebar-foot">FITNESS MEMBERSHIP<br /><span>V1 Completion</span></div>
      </aside>

      <main className="main-content" id="overview">
        <header className="topbar">
          <span>MEMBER DASHBOARD</span>
          <div className="topbar-actions">
            <a className="notification-shortcut" href="#notifications" aria-label={`Notifications, ${unreadNotifications} unread`}><Bell size={15} /> {unreadNotifications > 0 && <span>{unreadNotifications}</span>}</a>
            <span className="avatar" title={session.user.email}>{initials(session.user)}</span>
            <button className="sign-out-button" type="button" onClick={signOut}><LogOut size={14} /> Sign out</button>
          </div>
        </header>

        <section className="welcome">
          <p className="eyebrow">MEMBER SPACE · {session.user.role.toUpperCase()}</p>
          <h1>Good to see you, {session.user.full_name.split(' ')[0]}.</h1>
          <p className="subtle">Your membership access and visit history, in one place.</p>
        </section>

        {notice && <div className="notice-message dashboard-message"><CheckCircle2 size={16} />{notice}</div>}
        {error && <div className="error-message dashboard-message"><XCircle size={16} /><span>{error}</span></div>}

        {session.user.role === 'member' ? (
          <section className="hero-card" id="membership">
            <div className="hero-top">
              <span className="eyebrow">DIGITAL MEMBERSHIP PASS</span>
              <span className={`status-pill ${currentMembership ? 'is-active' : 'is-inactive'}`}>
                <span className="status-dot" />{currentMembership ? 'ACTIVE MEMBERSHIP' : 'NO ACTIVE MEMBERSHIP'}
              </span>
            </div>

            {currentMembership ? (
              <div className="pass-body">
                <div className="pass-copy">
                  <p className="eyebrow">MEMBERSHIP TIER</p>
                  <h2>{currentMembership.tier.charAt(0).toUpperCase() + currentMembership.tier.slice(1)}</h2>
                  <p className="pass-meta">Member ID · {session.user.id}</p>
                  <p className="pass-meta">Valid through · {humanDate(currentMembership.expiry_date)}</p>
                  <p className="pass-meta">Account · {session.user.email}</p>
                </div>
                {pass && !passExpired ? (
                  <div className="qr-live" aria-label="Secure short-lived gym entry QR code">
                    <QRCodeSVG value={pass.qr_token} size={132} bgColor="#f2f4e9" fgColor="#151712" level="M" includeMargin />
                    <small>TIME-LIMITED PASS</small>
                  </div>
                ) : (
                  <div className="qr-placeholder" aria-label="No active QR token generated"><ShieldCheck size={26} /><small>PASS NOT ISSUED</small></div>
                )}
              </div>
            ) : (
              <div className="empty-membership">
                <ShieldCheck size={25} />
                <div>
                  <h2>Membership access unavailable</h2>
                  <p className="pass-meta">No current active membership is linked to this account. Contact your club administrator to activate or renew your plan.</p>
                </div>
              </div>
            )}

            {currentMembership && (
              <>
                <button className="primary-button" type="button" onClick={generatePass} disabled={passBusy}>
                  {passBusy ? <LoaderCircle size={16} className="spin" /> : <ShieldCheck size={16} />}
                  {passBusy ? 'Generating secure pass…' : pass && !passExpired ? 'Refresh Digital Pass' : 'Generate Digital Pass'}
                  {!passBusy && <span>↗</span>}
                </button>
                {pass && (
                  <p className={`demo-note ${passExpired ? 'pass-warning' : ''}`}>
                    {passExpired ? 'This QR pass has expired. Generate a new pass before entering.' : `Pass expires at ${new Date(pass.expires_at).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })}. Keep this screen open for scanner validation.`}
                  </p>
                )}
              </>
            )}
            {!currentMembership && memberships.length > 0 && (
              <div className="membership-list">
                <p className="eyebrow">MEMBERSHIP RECORDS</p>
                {memberships.map((membership) => (
                  <div className="membership-row" key={membership.id}>
                    <span>{membership.tier} · {humanDate(membership.start_date)} – {humanDate(membership.expiry_date)}</span>
                    <strong>{membershipDisplayStatus(membership, today)}</strong>
                  </div>
                ))}
              </div>
            )}
          </section>
        ) : (
          <section className="hero-card">
            <div className="hero-top"><span className="eyebrow">STAFF ACCESS</span><span className="status-pill is-active"><span className="status-dot" /> SIGNED IN</span></div>
            <div className="empty-membership">
              <ShieldCheck size={25} />
              <div><h2>{session.user.role === 'admin' ? 'Administrator account' : 'Front-desk staff account'}</h2><p className="pass-meta">This account can use protected API endpoints. Member QR passes are only issued to member accounts.</p></div>
            </div>
            <a className="text-button docs-link" href={`${API_BASE}/docs`} target="_blank" rel="noreferrer">Open API operations console ↗</a>
          </section>
        )}

        <section className="section-head"><div><p className="eyebrow">YOUR ACTIVITY</p><h2>Membership snapshot</h2></div><button className="text-button refresh-link" type="button" onClick={refreshActivity}><RefreshCw size={13} /> Refresh data</button></section>
        <div className="stats-grid">
          <article className="stat-card">
            <span className="stat-icon"><Activity size={18} /></span>
            <p className="subtle">Visits this month</p>
            <strong>{visitsThisMonth.toString().padStart(2, '0')}</strong>
            <p className="tiny">Based on recorded successful check-ins</p>
          </article>
          <article className="stat-card">
            <span className="stat-icon"><CalendarDays size={18} /></span>
            <p className="subtle">Most recent check-in</p>
            <strong className="class-title">{latestCheckIn ? humanDate(latestCheckIn.checked_in_at) : 'No visits yet'}</strong>
            <p className="tiny">{latestCheckIn ? `${latestCheckIn.location_name || 'Gym'} · ${formatTimestamp(latestCheckIn.checked_in_at)}` : 'Your verified visits will appear here.'}</p>
          </article>
        </div>

        <section className="activity-panel" id="activity">
          <div className="section-head activity-title"><div><p className="eyebrow">RECENT ACTIVITY</p><h2>Check-in history</h2></div></div>
          {checkIns.length ? (
            <div className="activity-list">
              {checkIns.slice(0, 5).map((item) => (
                <div className="activity-row" key={item.id}>
                  <span className="activity-check"><CheckCircle2 size={16} /></span>
                  <div className="activity-detail"><strong>{item.location_name || 'Gym visit'}</strong><span>{formatTimestamp(item.checked_in_at)}</span></div>
                  <span className="activity-result">{item.result}</span>
                </div>
              ))}
            </div>
          ) : (
            <p className="empty-activity">No verified check-ins yet. Your successful gym entries will show here.</p>
          )}
        </section>

        <section className="account-panel" id="profile">
          <div className="section-head account-section-head"><div><p className="eyebrow">ACCOUNT DETAILS</p><h2>Profile</h2></div></div>
          <form className="settings-form" onSubmit={saveProfile}>
            <label>Full name<input className="settings-input" required minLength={1} maxLength={120} value={profileName} onChange={(event) => setProfileName(event.target.value)} /></label>
            <label>Email address<input className="settings-input" value={session.user.email} readOnly aria-describedby="email-readonly-note" /></label>
            <p id="email-readonly-note" className="tiny">Email changes require a separate verification workflow and are not enabled in V1.</p>
            <button className="secondary-button form-submit" type="submit" disabled={busy}><Save size={14} /> Save profile</button>
          </form>
        </section>

        <section className="account-panel" id="notifications">
          <div className="section-head account-section-head"><div><p className="eyebrow">ACCOUNT UPDATES</p><h2>Notifications {unreadNotifications > 0 && <span className="count-chip">{unreadNotifications} unread</span>}</h2></div>
            {unreadNotifications > 0 && <button className="text-button" type="button" onClick={markAllNotificationsRead}>Mark all as read</button>}
          </div>
          {notifications.length ? <div className="settings-list">
            {notifications.slice(0, 20).map((item) => <article className={`notification-row ${item.is_read ? 'is-read' : ''}`} key={item.id}>
              <span className="notification-icon"><Bell size={15} /></span>
              <div className="setting-list-copy"><strong>{item.title}</strong><p>{item.body}</p><small>{formatTimestamp(item.created_at)} · {item.category}</small></div>
              {!item.is_read && <button type="button" className="small-action" onClick={() => markNotificationRead(item.id)}>Mark read</button>}
            </article>)}
          </div> : <p className="empty-activity">No notifications yet. Important account and membership updates will appear here.</p>}
        </section>

        <section className="account-panel" id="privacy">
          <div className="section-head account-section-head"><div><p className="eyebrow">DATA & CONSENT</p><h2>Privacy preferences</h2></div></div>
          <p className="settings-description">Optional analytics and marketing use are off unless you enable them. Essential processing for authentication, membership access, security, and support remains necessary to provide the service.</p>
          <form className="settings-form" onSubmit={savePrivacy}>
            <label className="toggle-row"><span><strong>Product analytics</strong><small>Allow optional usage analytics to help improve member experiences.</small></span><input type="checkbox" checked={privacy.analytics_consent} onChange={(event) => setPrivacy((previous) => ({ ...previous, analytics_consent: event.target.checked }))} /></label>
            <label className="toggle-row"><span><strong>Product updates and offers</strong><small>Allow optional marketing communications about club products and offers.</small></span><input type="checkbox" checked={privacy.marketing_consent} onChange={(event) => setPrivacy((previous) => ({ ...previous, marketing_consent: event.target.checked }))} /></label>
            <p className="tiny">Consent schema: v1 · You can change these optional choices at any time.</p>
            <button className="secondary-button form-submit" type="submit" disabled={busy}><Save size={14} /> Save privacy preferences</button>
          </form>
        </section>

        <section className="account-panel" id="support">
          <div className="section-head account-section-head"><div><p className="eyebrow">WE CAN HELP</p><h2>Help & support</h2></div></div>
          <form className="settings-form" onSubmit={submitSupportTicket}>
            <label>Request category<select className="settings-input" value={supportForm.category} onChange={(event) => setSupportForm((previous) => ({ ...previous, category: event.target.value }))}>
              <option value="access">Gym access</option><option value="membership">Membership</option><option value="billing">Billing</option><option value="technical">Technical issue</option><option value="privacy">Privacy</option><option value="other">Other</option>
            </select></label>
            <label>Subject<input className="settings-input" required minLength={4} maxLength={140} value={supportForm.subject} onChange={(event) => setSupportForm((previous) => ({ ...previous, subject: event.target.value }))} placeholder="Briefly describe the issue" /></label>
            <label>Details<textarea className="settings-input" required minLength={10} maxLength={3000} rows={4} value={supportForm.message} onChange={(event) => setSupportForm((previous) => ({ ...previous, message: event.target.value }))} placeholder="Include the relevant details, but do not share your password." /></label>
            <button className="secondary-button form-submit" type="submit" disabled={busy}><Send size={14} /> Submit support request</button>
          </form>
          <div className="section-head account-section-head ticket-heading"><div><p className="eyebrow">YOUR REQUESTS</p><h2>Support history</h2></div></div>
          {supportTickets.length ? <div className="settings-list">{supportTickets.map((ticket) => <article className="ticket-row" key={ticket.id}>
            <div className="setting-list-copy"><strong>#{ticket.id} · {ticket.subject}</strong><p>{ticket.message}</p>{ticket.staff_response && <p className="staff-response"><b>Staff response:</b> {ticket.staff_response}</p>}<small>{formatTimestamp(ticket.created_at)} · {ticket.category}</small></div>
            <span className={`ticket-status status-${ticket.status}`}>{ticket.status.replace('_', ' ')}</span>
          </article>)}</div> : <p className="empty-activity">You have not submitted a support request yet.</p>}
        </section>

        <section className="api-card">
          <div className="api-copy"><p className="eyebrow">ACCOUNT SECURITY</p><h3>Signed in as {session.user.email}</h3><p className="api-message"><ShieldCheck size={15} /> Session token remains in memory only.</p></div>
          <button className="secondary-button" type="button" onClick={signOut}><LogOut size={15} /> Sign out</button>
        </section>
        <footer>FIT PULSE</footer>
      </main>
    </div>
  );
}

createRoot(document.getElementById('root')).render(<React.StrictMode><App /></React.StrictMode>);
