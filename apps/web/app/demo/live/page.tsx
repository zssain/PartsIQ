import { redirect } from "next/navigation";

// The earlier single-page demo console now lives in the unified workspace.
export default function LegacyLiveDemo(): never {
  redirect("/workspace?demo=1");
}
