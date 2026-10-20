import { redirect } from "next/navigation";

// Kept so existing links land on the current workspace screen.
export default function Legacy(): never {
  redirect("/workspace/admin/analytics");
}
