"use client";

import { useRouter } from "next/navigation";
import { useState, type JSX } from "react";

import { signInStaff } from "@/lib/auth";

// Invited-staff sign-in only. There is deliberately NO real-client self-signup here
// (CONSTRAINTS rule: public real-client signup disabled). The public demo uses anonymous
// sign-in from the landing page instead.
export default function LoginPage(): JSX.Element {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    try {
      await signInStaff(email, password);
      router.push("/staff/inbox");
    } catch {
      setError("Sign in failed. Check your invited staff credentials.");
    }
  }

  return (
    <main>
      <h1>Staff sign in</h1>
      <p>Invited staff only. Customers use “Start demo” on the home page — there is no public signup.</p>
      <form onSubmit={onSubmit}>
        <label>
          Email
          <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
        </label>
        <label>
          Password
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
        </label>
        <button type="submit">Sign in</button>
      </form>
      {error ? <p role="alert">{error}</p> : null}
    </main>
  );
}
