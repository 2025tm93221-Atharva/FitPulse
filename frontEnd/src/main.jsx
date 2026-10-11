import React, { useEffect, useMemo, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { QRCodeSVG } from 'qrcode.react';
import {
  Activity,
  CalendarDays,
  CheckCircle2,
  CreditCard,
  Dumbbell,
  KeyRound,
  LoaderCircle,
  LogOut,
  RefreshCw,
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
  const [mode, setMode] = useState('login');
  const [form, setForm] = useState({ email: '', password: '', full_name: '' });
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
    const [membershipData, checkInData] = await Promise.all([
      apiFetch('/api/memberships/me', {}, accessToken),
      apiFetch('/api/check-ins/me', {}, accessToken),
    ]);
    setMemberships(membershipData);
    setCheckIns(checkInData);
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
          <h1>{mode === 'login' ? 'Welcome back.' : 'Join your club.'}</h1>
          <p className="auth-subtitle">
            {mode === 'login'
              ? 'Sign in to view your membership and secure digital pass.'
              : 'Create your member account. Your club must assign a membership before gym entry is enabled.'}
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
            <button className="primary-button auth-submit" type="submit" disabled={busy}>
              {busy ? <LoaderCircle className="spin" size={16} /> : mode === 'login' ? <KeyRound size={16} /> : <UserRound size={16} />}
              {busy ? 'Please wait…' : mode === 'login' ? 'Sign In' : 'Create Account'}
            </button>
          </form>

          <div className="auth-switch">
            <span>{mode === 'login' ? 'New to your club?' : 'Already have an account?'}</span>
            <button type="button" onClick={() => { setMode(mode === 'login' ? 'register' : 'login'); setError(''); setNotice(''); }}>
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
        <div className="sidebar-foot">FITNESS MEMBERSHIP<br /></div>
      </aside>

      <main className="main-content" id="overview">
        <header className="topbar">
          <span>MEMBER DASHBOARD</span>
          <div className="topbar-actions">
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

        <section className="api-card">
          <div className="api-copy"><p className="eyebrow">ACCOUNT SECURITY</p><h3>Signed in as {session.user.email}</h3><p className="api-message"><ShieldCheck size={15} /> Session token remains in memory only.</p></div>
          <button className="secondary-button" type="button" onClick={signOut}><LogOut size={15} /> Sign out</button>
        </section>
        <footer>FIT PULSE </footer>
      </main>
    </div>
  );
}

createRoot(document.getElementById('root')).render(<React.StrictMode><App /></React.StrictMode>);
