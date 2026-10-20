import { redirect } from "next/navigation";

// Kept so existing links land on the current enquiry screen.
export default async function LegacyChat({ params }: { params: Promise<{ id: string }> }): Promise<never> {
  const { id } = await params;
  redirect(`/workspace/enquiries/${encodeURIComponent(id)}`);
}
