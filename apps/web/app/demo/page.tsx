import { redirect } from "next/navigation";

// "Try demo": the public recruiter demo is the real workspace in a private synthetic sandbox.
export default function TryDemo(): never {
  redirect("/workspace?demo=1");
}
