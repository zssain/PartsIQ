import { redirect } from "next/navigation";

// Kept so existing links land on the current review workspace.
export default async function LegacyReview({ params }: { params: Promise<{ id: string }> }): Promise<never> {
  const { id } = await params;
  redirect(`/workspace/review/${encodeURIComponent(id)}`);
}
