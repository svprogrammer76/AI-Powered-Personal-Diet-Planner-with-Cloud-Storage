import React, { useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import { api, apiBlob, clearToken, getToken, setToken } from "./api.js";
import "./styles.css";
import "./overrides.css";

function App() {
  const [token, setAuth] = useState(getToken());
  const [page, setPage] = useState("dashboard");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [profile, setProfile] = useState(null);
  const [plans, setPlans] = useState([]);
  const [files, setFiles] = useState([]);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [authMode, setAuthMode] = useState("login");
  const [voiceState, setVoiceState] = useState("idle");
  const [transcript, setTranscript] = useState("");
  const [answer, setAnswer] = useState("");
  const [askBusy, setAskBusy] = useState(false);
  const [speechBusy, setSpeechBusy] = useState(false);
  const [speechLanguage, setSpeechLanguage] = useState("auto");
  const [audioUrl, setAudioUrl] = useState("");
  const voiceSession = useRef(null);

  async function refresh() {
    if (!token) return;
    try {
      const [p, ps, fs] = await Promise.all([
        api("/profile").catch(() => null), api("/plans"), api("/files")
      ]);
      setProfile(p); setPlans(ps); setFiles(fs);
    } catch (e) { setError(e.message); }
  }
  useEffect(() => { refresh(); }, [token]);
  useEffect(() => () => {
    const session = voiceSession.current;
    if (session) { session.stream.getTracks().forEach(track => track.stop()); session.context.close(); }
  }, []);
  useEffect(() => () => { if (audioUrl) URL.revokeObjectURL(audioUrl); }, [audioUrl]);

  async function startVoiceRecording() {
    setError(""); setNotice(""); setTranscript(""); setAnswer(""); setAudioUrl("");
    if (!navigator.mediaDevices?.getUserMedia || !window.AudioContext) {
      setError("Voice recording is not supported in this browser. Try a current version of Chrome, Edge, or Firefox."); return;
    }
    let stream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true } });
      const context = new AudioContext();
      const source = context.createMediaStreamSource(stream);
      const processor = context.createScriptProcessor(4096, 1, 1);
      const chunks = [];
      processor.onaudioprocess = event => {
        chunks.push(new Float32Array(event.inputBuffer.getChannelData(0)));
        event.outputBuffer.getChannelData(0).fill(0);
      };
      source.connect(processor); processor.connect(context.destination);
      const session = { stream, context, source, processor, chunks, startedAt: Date.now(), timer: null };
      voiceSession.current = session;
      setVoiceState("recording");
      session.timer = window.setTimeout(() => stopVoiceRecording(), 15000);
    } catch (err) {
      stream?.getTracks().forEach(track => track.stop());
      if (err?.name === "NotAllowedError" || err?.name === "PermissionDeniedError") setError("Microphone access was blocked. Allow microphone permission in your browser settings, then try again.");
      else if (err?.name === "NotFoundError" || err?.name === "DevicesNotFoundError") setError("No microphone was found. Connect a microphone and try again.");
      else setError("Could not start the microphone. Check your audio device and try again.");
      setVoiceState("idle");
    }
  }

  async function stopVoiceRecording() {
    const session = voiceSession.current;
    if (!session) return;
    voiceSession.current = null;
    window.clearTimeout(session.timer);
    session.processor.disconnect(); session.source.disconnect();
    session.stream.getTracks().forEach(track => track.stop());
    await session.context.close();
    const duration = (Date.now() - session.startedAt) / 1000;
    if (duration < 1 || !session.chunks.length) { setVoiceState("idle"); setError("That recording was too short. Hold the button and speak for at least one second."); return; }
    setVoiceState("transcribing");
    try {
      const wav = encodeWav(session.chunks, session.context.sampleRate);
      const form = new FormData(); form.append("audio_file", wav, "question.wav");
      const result = await api("/transcribe", { method: "POST", body: form });
      setTranscript(result.transcript);
      setNotice("Transcript ready. Review or edit your question below.");
    } catch (err) { setError(err.message || "Transcription failed. Please try again."); }
    finally { setVoiceState("idle"); }
  }

  async function askQuestion() {
    const question = transcript.trim();
    if (!question) { setError("Record a question or type one into the transcript first."); return; }
    setError(""); setNotice(""); setAnswer(""); setAskBusy(true);
    try {
      const result = await api("/ask", { method: "POST", body: JSON.stringify({ question }) });
      setAnswer(result.answer); setAudioUrl("");
    } catch (err) { setError(err.message || "The AI reply could not be generated. Please try again."); }
    finally { setAskBusy(false); }
  }

  async function speakAnswer() {
    if (!answer.trim()) return;
    setError(""); setAudioUrl(""); setSpeechBusy(true);
    try {
      const audio = await apiBlob("/speak", { method: "POST", body: JSON.stringify({ text: answer, language: speechLanguage }) });
      setAudioUrl(URL.createObjectURL(audio));
    } catch (err) { setError(err.message || "Gnani Timbre could not generate audio. Please try again."); }
    finally { setSpeechBusy(false); }
  }

  async function authenticate(e) {
    e.preventDefault(); setError(""); setBusy(true);
    try {
      const result = await api(`/${authMode === "login" ? "login" : "register"}`, { method: "POST", body: JSON.stringify({ email, password }) });
      if (result.access_token) { setToken(result.access_token); setAuth(result.access_token); }
      else setNotice("Check your email to confirm the account, then log in.");
    } catch (e) { setError(e.message); } finally { setBusy(false); }
  }
  function logout() { clearToken(); setAuth(null); setProfile(null); setPlans([]); setFiles([]); }
  async function saveProfile(e) {
    e.preventDefault(); setError(""); setBusy(true);
    const form = new FormData(e.currentTarget);
    const value = Object.fromEntries(form.entries());
    value.age = Number(value.age); value.height_cm = Number(value.height_cm); value.weight_kg = Number(value.weight_kg);
    value.allergies = value.allergies ? value.allergies.split(",").map(x => x.trim()).filter(Boolean) : [];
    try { setProfile(await api("/profile", { method: "PUT", body: JSON.stringify(value) })); setNotice("Profile saved."); }
    catch (e) { setError(e.message); } finally { setBusy(false); }
  }
  async function generate() {
    setBusy(true); setError("");
    try { await api("/generate-plan", { method: "POST" }); await refresh(); setNotice("Your educational example plan has been saved."); setPage("plans"); }
    catch (e) { setError(e.message); } finally { setBusy(false); }
  }
  async function upload(e) {
    const file = e.target.files?.[0]; if (!file) return;
    const data = new FormData(); data.append("file", file); setError("");
    try { await api("/upload", { method: "POST", body: data }); await refresh(); setNotice("Image uploaded."); }
    catch (err) { setError(err.message); }
    e.target.value = "";
  }
  async function download(item) {
    try {
      const response = await fetch(`${import.meta.env.VITE_API_BASE || "http://localhost:8000"}/files/${item.file_id}/download`, { headers: { Authorization: `Bearer ${token}` } });
      if (!response.ok) throw new Error("Download failed");
      const url = URL.createObjectURL(await response.blob()); const a = document.createElement("a"); a.href = url; a.download = item.filename; a.click(); URL.revokeObjectURL(url);
    } catch (e) { setError(e.message); }
  }
  async function removePlan(plan) {
    try { await api(`/plans/${plan.plan_id}`, { method: "DELETE" }); await refresh(); setNotice("Plan deleted."); }
    catch (e) { setError(e.message); }
  }
  const latest = plans[0];

  if (!token) return <main className="auth-shell"><section className="auth-copy"><div className="brand"><span className="brand-mark">dt</span> daily table</div><p className="eyebrow">YOUR EVERYDAY WELLNESS COMPANION</p><h1>Make room for<br/><em>good food.</em></h1><p>Simple meal inspiration, saved privately for your next day.</p><small>Educational examples only. Not medical or clinical nutrition advice.</small></section><form className="auth-card" onSubmit={authenticate}><p className="eyebrow">WELCOME</p><h2>{authMode === "login" ? "Sign in to your account" : "Create your account"}</h2><label>Email<input required type="email" value={email} onChange={e => setEmail(e.target.value)} placeholder="you@example.com"/></label><label>Password<input required minLength="8" type="password" value={password} onChange={e => setPassword(e.target.value)} placeholder="At least 8 characters"/></label><button className="primary" disabled={busy}>{busy ? "Please wait…" : authMode === "login" ? "Sign in" : "Create account"}</button><p className="switch">{authMode === "login" ? "New here?" : "Already have an account?"} <button type="button" className="text-button" onClick={() => setAuthMode(authMode === "login" ? "register" : "login")}>{authMode === "login" ? "Create an account" : "Sign in"}</button></p>{error && <p className="error">{error}</p>}{notice && <p className="success">{notice}</p>}</form></main>;

  return <div className="app-shell"><aside className="sidebar"><div className="brand"><span className="brand-mark">dt</span> daily table</div><p className="nav-label">YOUR SPACE</p>{[["dashboard","Overview"],["profile","My profile"],["plans","Saved plans"],["files","My files"]].map(([id,label])=><button key={id} className={`nav-item ${page===id?"active":""}`} onClick={()=>setPage(id)}>{label}</button>)}<div className="side-bottom"><div className="avatar">{(profile?.name || email || "U").slice(0,1).toUpperCase()}</div><div className="account">{profile?.name || email}<small>Personal account</small></div><button className="logout" onClick={logout}>Log out</button></div></aside><main className="main"><header className="topbar"><span>Personal wellness</span><span className="date-label">A little inspiration for today</span></header><div className="content">{error && <div className="alert error">{error}<button onClick={()=>setError("")}>×</button></div>}{notice && <div className="alert success">{notice}<button onClick={()=>setNotice("")}>×</button></div>}
  {page === "dashboard" && <><p className="eyebrow">YOUR DASHBOARD</p><h1>{profile?.name ? `Welcome, ${profile.name.split(" ")[0]}` : "Welcome to your table"}</h1><p className="subhead">A calm place to plan your next meal.</p><VoiceCard voiceState={voiceState} transcript={transcript} setTranscript={setTranscript} answer={answer} askBusy={askBusy} speechBusy={speechBusy} speechLanguage={speechLanguage} setSpeechLanguage={setSpeechLanguage} audioUrl={audioUrl} onSpeak={speakAnswer} onAsk={askQuestion} onStart={startVoiceRecording} onStop={stopVoiceRecording}/><div className="hero-card"><div><p className="eyebrow">YOUR NEXT STEP</p><h2>{profile ? "Ready for a fresh idea?" : "Start with your profile"}</h2><p>{profile ? "Create a general meal-plan example using your preferences." : "Add your preferences to personalize your experience."}</p><button className="primary" onClick={()=>profile?generate():setPage("profile")} disabled={busy}>{busy?"Working…":profile?"Generate a plan →":"Complete your profile →"}</button></div><div className="hero-art">✳</div></div><div className="stats"><div className="stat-card"><span>YOUR GOAL</span><strong>{profile?.goal?.replaceAll("_"," ") || "Not set yet"}</strong></div><div className="stat-card"><span>FOOD STYLE</span><strong>{profile?.dietary_preference || "Not set yet"}</strong></div><div className="stat-card"><span>SAVED PLANS</span><strong>{plans.length}</strong></div><button className="stat-card stat-button" onClick={()=>setPage("files")}><span>UPLOADED FILES</span><strong>{files.length}</strong></button></div><section className="section-heading"><div><p className="eyebrow">RECENTLY SAVED</p><h2>Your plans</h2></div><button className="link-button" onClick={()=>setPage("plans")}>See all →</button></section>{latest?<PlanCard plan={latest} onDelete={()=>removePlan(latest)}/>:<div className="empty">Your saved plans will appear here.</div>}<p className="disclaimer">Meal suggestions are general educational examples and are not medical advice.</p></>}
  {page === "profile" && <><p className="eyebrow">YOUR DETAILS</p><h1>My profile</h1><p className="subhead">Use demo information only. Fields help tailor general suggestions.</p><form className="form-card" onSubmit={saveProfile}><div className="form-grid"><label>Name<input name="name" required defaultValue={profile?.name || ""}/></label><label>Age<input name="age" required type="number" min="13" max="110" defaultValue={profile?.age || ""}/></label><label>Height (cm)<input name="height_cm" required type="number" min="81" max="250" step="0.1" defaultValue={profile?.height_cm || ""}/></label><label>Weight (kg)<input name="weight_kg" required type="number" min="26" max="350" step="0.1" defaultValue={profile?.weight_kg || ""}/></label><label>Activity level<select name="activity_level" defaultValue={profile?.activity_level || "moderate"}><option value="low">Low</option><option value="moderate">Moderate</option><option value="high">High</option></select></label><label>Food preference<select name="dietary_preference" defaultValue={profile?.dietary_preference || "general"}><option value="general">General / non-vegetarian</option><option value="vegetarian">Vegetarian</option><option value="vegan">Vegan</option></select></label><label>Your goal<select name="goal" defaultValue={profile?.goal || "balanced"}><option value="balanced">Balanced eating</option><option value="weight_management">Weight-management demo</option><option value="fitness">Fitness-oriented demo</option></select></label><label className="full">Allergies or foods to avoid <span className="hint">comma-separated</span><input name="allergies" defaultValue={profile?.allergies?.join(", ") || ""}/></label></div><button className="primary" disabled={busy}>{busy?"Saving…":"Save profile"}</button><p className="disclaimer">This application does not diagnose conditions or provide clinical nutrition advice.</p></form></>}
  {page === "plans" && <><p className="eyebrow">YOUR LIBRARY</p><h1>Saved plans</h1><p className="subhead">Examples you can revisit whenever you need inspiration.</p>{plans.length?plans.map(p=><PlanCard key={p.plan_id} plan={p} onDelete={()=>removePlan(p)}/>):<div className="empty">No plans yet. Complete your profile, then generate one from the dashboard.</div>}</>}
  {page === "files" && <><p className="eyebrow">YOUR CLOUD FILES</p><h1>Meal inspiration</h1><p className="subhead">Upload an optional food or meal image. JPEG, PNG, or WebP up to 5 MB.</p><label className="upload-button">＋ Choose an image<input hidden type="file" accept="image/jpeg,image/png,image/webp" onChange={upload}/></label><div className="file-list">{files.map(f=><div className="file-row" key={f.file_id}><span className="file-icon">▧</span><div><strong>{f.filename}</strong><small>Uploaded {new Date(f.uploaded_at).toLocaleDateString()}</small></div><button className="link-button" onClick={()=>download(f)}>Download</button><button className="danger-link" onClick={async()=>{await api(`/files/${f.file_id}`,{method:"DELETE"});refresh();}}>Delete</button></div>)}{!files.length&&<div className="empty">Your private uploads will appear here.</div>}</div></>}
  </div></main></div>;
}

function encodeWav(chunks, inputRate) {
  const targetRate = 16000;
  const total = chunks.reduce((sum, chunk) => sum + chunk.length, 0);
  const source = new Float32Array(total); let offset = 0;
  chunks.forEach(chunk => { source.set(chunk, offset); offset += chunk.length; });
  const ratio = inputRate / targetRate;
  const length = Math.floor(source.length / ratio);
  const buffer = new ArrayBuffer(44 + length * 2); const view = new DataView(buffer);
  const write = (position, value) => [...value].forEach((char, index) => view.setUint8(position + index, char.charCodeAt(0)));
  write(0, "RIFF"); view.setUint32(4, 36 + length * 2, true); write(8, "WAVE"); write(12, "fmt ");
  view.setUint32(16, 16, true); view.setUint16(20, 1, true); view.setUint16(22, 1, true);
  view.setUint32(24, targetRate, true); view.setUint32(28, targetRate * 2, true);
  view.setUint16(32, 2, true); view.setUint16(34, 16, true); write(36, "data"); view.setUint32(40, length * 2, true);
  for (let i = 0; i < length; i++) {
    const start = Math.floor(i * ratio); const end = Math.min(Math.floor((i + 1) * ratio), source.length);
    let sample = 0; for (let j = start; j < end; j++) sample += source[j];
    sample = Math.max(-1, Math.min(1, sample / Math.max(1, end - start)));
    view.setInt16(44 + i * 2, sample < 0 ? sample * 0x8000 : sample * 0x7fff, true);
  }
  return new Blob([buffer], { type: "audio/wav" });
}

function VoiceCard({voiceState, transcript, setTranscript, answer, askBusy, speechBusy, speechLanguage, setSpeechLanguage, audioUrl, onSpeak, onAsk, onStart, onStop}) {
  return <section className="voice-card"><div className="voice-intro"><p className="eyebrow">VOICE QUESTION & ANSWER · GNANI PRISMA + GEMINI + TIMBRE</p><h2>Ask your meal question</h2><p>Record a short question, review the transcript, then get a concise general wellness reply.</p></div><button className={`voice-button ${voiceState === "recording" ? "recording" : ""}`} onClick={voiceState === "recording" ? onStop : onStart} disabled={voiceState === "transcribing" || askBusy}>{voiceState === "recording" ? "■ Stop recording" : voiceState === "transcribing" ? "Transcribing…" : "● Ask by voice"}</button>{transcript && <><label className="transcript-field">Prisma transcript — edit before sending<textarea rows={3} value={transcript} onChange={e=>setTranscript(e.target.value)} aria-label="Editable voice transcript"/><span>Review and edit the transcript before sending your question.</span></label><div className="ask-actions"><button className="primary" onClick={onAsk} disabled={askBusy || !transcript.trim()}>{askBusy ? "Getting a reply…" : "Send question"}</button><span>Uses your food preference and latest sample plan when available.</span></div></>}{answer && <div className="voice-answer" aria-live="polite"><p className="eyebrow">AI REPLY · GEMINI</p><p>{answer}</p><div className="speech-controls"><button className="speak-button" onClick={onSpeak} disabled={speechBusy}>{speechBusy ? "Generating audio…" : audioUrl ? "↻ Generate audio again" : "▶ Speak this reply"}</button><label className="speech-language">Speech language<select value={speechLanguage} onChange={e=>setSpeechLanguage(e.target.value)}><option value="auto">Auto detect</option><option value="hi-IN">Hindi</option><option value="en-IN">English (India)</option></select></label></div>{audioUrl && <div className="audio-player"><span>Generated by Gnani Timbre v3.0</span><audio controls preload="none" src={audioUrl}>Audio playback is not supported in this browser.</audio></div>}<small>General wellness information only. Not medical advice.</small></div>}</section>;
}
function PlanCard({plan,onDelete}) { function exportPlan(){const text=`# Educational meal plan\n\nDate: ${new Date(plan.created_at).toLocaleDateString()}\n\n- Breakfast: ${plan.breakfast}\n- Lunch: ${plan.lunch}\n- Snack: ${plan.snack}\n- Dinner: ${plan.dinner}\n\nGeneral nutrition note: ${plan.nutrition_summary}\n\nHydration: ${plan.hydration_reminder}\n\n${plan.educational_notice}\n`;const url=URL.createObjectURL(new Blob([text],{type:"text/markdown"}));const a=document.createElement("a");a.href=url;a.download=`meal-plan-${plan.plan_id.slice(0,8)}.md`;a.click();URL.revokeObjectURL(url);}return <article className="plan-card"><div className="plan-meta"><span>MEAL PLAN</span><span>{new Date(plan.created_at).toLocaleDateString()}</span></div><div className="meal-grid">{[["BREAKFAST",plan.breakfast],["LUNCH",plan.lunch],["SNACK",plan.snack],["DINNER",plan.dinner]].map(([label,value])=><div key={label}><span>{label}</span><p>{value}</p></div>)}</div><div className="summary"><strong>General nutrition note</strong><p>{plan.nutrition_summary}</p><p>{plan.hydration_reminder}</p><small>{plan.educational_notice} · Generated with {plan.source} engine.</small></div><div className="plan-actions"><button className="link-button" onClick={exportPlan}>Download plan</button>{onDelete&&<button className="danger-link" onClick={onDelete}>Delete plan</button>}</div></article>; }

createRoot(document.getElementById("root")).render(<App/>);
