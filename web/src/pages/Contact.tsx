import { useRef, useState } from "react";

const GITHUB = "https://github.com/oncomap/oncomap";

// Client-side rate limit: block a re-submit within this window of the last one.
// Belt-and-braces over the honeypot; true per-IP limiting is Netlify's layer.
const COOLDOWN_MS = 30_000;
const DATASET_ISSUE = `${GITHUB}/issues/new?template=add-a-dataset.yml`;
const REPORT_RECORD = `${GITHUB}/blob/main/docs/INCIDENT_RESPONSE.md`;

// Netlify Forms: submissions POST (url-encoded) to the site root with a
// form-name matching the static stub in index.html. Netlify emails them to the
// address configured under Forms -> Notifications and stores them in the
// dashboard. No third-party service or client-side key.
const FORM_NAME = "contact";

function encodeForm(data: Record<string, string>): string {
  return Object.entries(data)
    .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(v)}`)
    .join("&");
}

const ROLES = [
  "Researcher",
  "Clinician",
  "Data submitter",
  "Industry",
  "Student",
  "Other",
];
const INQUIRY_TYPES = [
  "Collaboration or partnership",
  "Dataset correction",
  "Bug or site issue",
  "Data reuse question",
  "Media or press",
  "Other",
];

interface FormState {
  name: string;
  email: string;
  organization: string;
  role: string;
  inquiry_type: string;
  dataset: string;
  message: string;
  consent: boolean;
  botcheck: string; // honeypot: real users leave it empty
}

const EMPTY: FormState = {
  name: "",
  email: "",
  organization: "",
  role: "",
  inquiry_type: "",
  dataset: "",
  message: "",
  consent: false,
  botcheck: "",
};

type Errors = Partial<Record<keyof FormState, string>>;
type Status = "idle" | "sending" | "success" | "error" | "cooldown";

function validate(f: FormState): Errors {
  const e: Errors = {};
  if (!f.name.trim()) e.name = "Please enter your name.";
  if (!f.email.trim()) e.email = "Please enter your email.";
  else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(f.email.trim()))
    e.email = "Please enter a valid email address.";
  if (!f.inquiry_type) e.inquiry_type = "Please choose an inquiry type.";
  if (!f.message.trim()) e.message = "Please enter a message.";
  if (!f.consent)
    e.consent = "Please confirm we may use your details to reply.";
  return e;
}

export default function Contact() {
  const [form, setForm] = useState<FormState>(EMPTY);
  const [errors, setErrors] = useState<Errors>({});
  const [status, setStatus] = useState<Status>("idle");
  const lastSubmit = useRef(0);

  function set<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((f) => ({ ...f, [key]: value }));
    if (errors[key]) setErrors((e) => ({ ...e, [key]: undefined }));
  }

  async function onSubmit(ev: React.FormEvent) {
    ev.preventDefault();
    const e = validate(form);
    setErrors(e);
    if (Object.keys(e).length > 0) return;
    if (form.botcheck) return; // silently drop bots

    const now = Date.now();
    if (now - lastSubmit.current < COOLDOWN_MS) {
      setStatus("cooldown");
      return;
    }
    lastSubmit.current = now;

    setStatus("sending");
    try {
      const res = await fetch("/", {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: encodeForm({
          "form-name": FORM_NAME,
          name: form.name.trim(),
          email: form.email.trim(),
          organization: form.organization.trim(),
          role: form.role,
          inquiry_type: form.inquiry_type,
          dataset: form.dataset.trim(),
          message: form.message.trim(),
          consent: form.consent ? "yes" : "no",
          botcheck: "",
        }),
      });
      if (res.ok) {
        setStatus("success");
        setForm(EMPTY);
      } else {
        setStatus("error");
      }
    } catch {
      setStatus("error");
    }
  }

  const err = (k: keyof FormState) =>
    errors[k] ? (
      <span className="field-error" id={`${k}-error`}>
        {errors[k]}
      </span>
    ) : null;

  return (
    <main className="wrap contact-page">
      <h1 className="page-title">Contact</h1>
      <p className="prose">
        Questions, corrections, collaborations, or press - send a note and we
        will get back to you. To propose a dataset, please use the structured
        issue form instead.
      </p>

      <div className="callout">
        <strong>Proposing a dataset?</strong> Use the{" "}
        <a href={DATASET_ISSUE} target="_blank" rel="noopener noreferrer" className="acc">
          Add a dataset issue form
        </a>{" "}
        - its fields map straight to a record. To flag a wrong or dead record,
        see{" "}
        <a href={REPORT_RECORD} target="_blank" rel="noopener noreferrer" className="acc">
          reporting a record
        </a>
        .
      </div>

      <form
        className="contact-form"
        name={FORM_NAME}
        method="POST"
        data-netlify="true"
        data-netlify-honeypot="botcheck"
        onSubmit={onSubmit}
        noValidate
      >
        <input type="hidden" name="form-name" value={FORM_NAME} />
        <div className="form-grid">
          <div className="control">
            <label htmlFor="name">
              Name <span className="req">*</span>
            </label>
            <input
              id="name"
              type="text"
              value={form.name}
              onChange={(e) => set("name", e.target.value)}
              aria-invalid={!!errors.name}
              aria-describedby={errors.name ? "name-error" : undefined}
            />
            {err("name")}
          </div>
          <div className="control">
            <label htmlFor="email">
              Email <span className="req">*</span>
            </label>
            <input
              id="email"
              type="email"
              value={form.email}
              onChange={(e) => set("email", e.target.value)}
              aria-invalid={!!errors.email}
              aria-describedby={errors.email ? "email-error" : undefined}
            />
            {err("email")}
          </div>
          <div className="control">
            <label htmlFor="organization">Organization / affiliation</label>
            <input
              id="organization"
              type="text"
              value={form.organization}
              onChange={(e) => set("organization", e.target.value)}
            />
          </div>
          <div className="control">
            <label htmlFor="role">Role</label>
            <select
              id="role"
              value={form.role}
              onChange={(e) => set("role", e.target.value)}
            >
              <option value="">Select...</option>
              {ROLES.map((r) => (
                <option key={r} value={r}>
                  {r}
                </option>
              ))}
            </select>
          </div>
          <div className="control">
            <label htmlFor="inquiry_type">
              Inquiry type <span className="req">*</span>
            </label>
            <select
              id="inquiry_type"
              value={form.inquiry_type}
              onChange={(e) => set("inquiry_type", e.target.value)}
              aria-invalid={!!errors.inquiry_type}
              aria-describedby={
                errors.inquiry_type ? "inquiry_type-error" : undefined
              }
            >
              <option value="">Select...</option>
              {INQUIRY_TYPES.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
            {err("inquiry_type")}
          </div>
          <div className="control">
            <label htmlFor="dataset">Related dataset ID / accession</label>
            <input
              id="dataset"
              type="text"
              placeholder="e.g. GSE267401 or a catalog id"
              value={form.dataset}
              onChange={(e) => set("dataset", e.target.value)}
            />
          </div>
        </div>

        <div className="control control--full">
          <label htmlFor="message">
            Message <span className="req">*</span>
          </label>
          <textarea
            id="message"
            rows={6}
            value={form.message}
            onChange={(e) => set("message", e.target.value)}
            aria-invalid={!!errors.message}
            aria-describedby={errors.message ? "message-error" : undefined}
          />
          {err("message")}
        </div>

        <input
          type="text"
          name="botcheck"
          className="honeypot"
          tabIndex={-1}
          autoComplete="off"
          aria-hidden="true"
          value={form.botcheck}
          onChange={(e) => set("botcheck", e.target.value)}
        />

        <div className="consent-row">
          <input
            id="consent"
            type="checkbox"
            checked={form.consent}
            onChange={(e) => set("consent", e.target.checked)}
            aria-invalid={!!errors.consent}
            aria-describedby={errors.consent ? "consent-error" : undefined}
          />
          <label htmlFor="consent">
            I agree that my details may be used to respond to this inquiry.{" "}
            <span className="req">*</span>
          </label>
        </div>
        {err("consent")}

        <div className="form-actions">
          <button
            type="submit"
            className="btn btn--primary"
            disabled={status === "sending"}
          >
            {status === "sending" ? "Sending..." : "Send message"}
          </button>
          <span className="privacy-note">
            Your details are used only to reply, and are handled by Netlify
            Forms.
          </span>
        </div>

        <div aria-live="polite">
          {status === "success" && (
            <div className="form-status form-status--ok" role="status">
              Thanks - your message has been sent. We will be in touch.
            </div>
          )}
          {status === "cooldown" && (
            <div className="form-status form-status--error" role="status">
              Please wait a moment before sending another message.
            </div>
          )}
          {status === "error" && (
            <div className="form-status form-status--error" role="status">
              Something went wrong sending your message. Please try again, or{" "}
              <a
                href={`${GITHUB}/issues/new`}
                target="_blank"
                rel="noopener noreferrer"
                className="acc"
              >
                open a GitHub issue
              </a>
              .
            </div>
          )}
        </div>
      </form>
    </main>
  );
}
